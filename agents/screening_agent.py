from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore
from langchain_core.messages import HumanMessage, SystemMessage
from .job_description import JOB_DESCRIPTION
from dotenv import load_dotenv
from langchain_core.callbacks import get_usage_metadata_callback
from prompts.screening_agent_prompts import FEEDBACK_AGENT_PROMPT, DECIDER_AGENT_PROMPT
import hashlib
import json
import time
import uuid

load_dotenv()


def memory_namespace(user_id: str, job_description: str) -> tuple[str, str]:
    """Namespace labels for the long-term store. Hashed because store namespace labels
    can't contain periods (or other special characters), which real user_ids like emails do.
    """
    user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
    jd_hash = hashlib.sha256(job_description.encode()).hexdigest()[:16]
    return (user_hash, jd_hash)

'''
Screening Graph:
Start -> Generate Questions -> Ask Questions -> Compile Feedback Input -> [Feedback Agent, Decider Agent] (parallel) -> End

Generate Questions:
    - Generate 5 questions for the user to answer

Ask Questions (Interviewer Agent):
    - Ask the questions to the user one at a time via interrupt()
    - Save answers in state

Compile Feedback Input:
    - Build the question -> answer mapping once, shared by both downstream agents

Feedback Agent:
    - Runs in parallel with Decider Agent
    - Generates qualitative feedback on the candidate's answers

Decider Agent:
    - Runs in parallel with Feedback Agent
    - Returns a pass/fail decision

End:
    - Returns the pass/fail decision and the feedback
'''

class QuestionFormat(TypedDict):
    question1: str
    question2: str
    question3: str
    question4: str
    question5: str

class FeedbackOutput(TypedDict):
    feedback: str

class DecisionOutput(TypedDict):
    result: bool


class ScreeningAgent(TypedDict):
    result: DecisionOutput          # the result of the screening
    questions: QuestionFormat       # the questions to ask the user
    job_description: str            # the job description
    responses: list
    feedback_input: dict
    feedback_output: FeedbackOutput
    user_id: str
    menu_choice: str
    previous_attempt: dict


def generate_questions(state: ScreeningAgent) -> dict:
    """Generate questions for the user to answer"""
    model = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.0,
    )
    model = model.with_structured_output(QuestionFormat, method="json_schema")

    response = model.invoke([
        SystemMessage(
            content=[{
                "type": "text",
                "text": "You are a helpful assistant that generates 5 questions for an initial screening interview.",
            }]
        ),
        HumanMessage(content=[{
            "type": "text",
            "text": f"Generate questions based on job description: {state['job_description']}",
            "cache_control": {"type": "ephemeral"}
        }])
    ])

    return {"questions": response}


def ask_questions(state: ScreeningAgent) -> dict:
    """Ask the questions to the user, one at a time, pausing for each answer"""
    questions = state["questions"]
    responses = state.get("responses", [])

    idx = len(responses)
    keys = list(questions.keys())
    if idx >= len(keys):
        return {"responses": responses}

    current_key = keys[idx]
    answer = interrupt({"question": questions[current_key], "question_key": current_key})

    responses = responses + [answer]
    return {"responses": responses}


def should_continue_asking(state: ScreeningAgent) -> str:
    if len(state.get("responses", [])) < len(state["questions"]):
        return "ask_questions"
    return "compile_feedback_input"


async def compile_feedback_input(state: ScreeningAgent, *, store: BaseStore) -> dict:
    """Build the question -> answer mapping once, shared by both downstream agents.

    Also looks up the most recent prior attempt (if any) for this user + job description
    so the downstream agents can judge improvement rather than scoring in isolation.
    """
    questions = state["questions"]
    responses = state["responses"]
    feedback_input = {}
    for i, key in enumerate(questions):
        feedback_input[questions[key]] = responses[i]

    namespace = memory_namespace(state["user_id"], state["job_description"])
    items = await store.asearch(namespace)

    previous_attempt = None
    if items:
        previous_attempt = max(items, key=lambda item: item.value["timestamp"]).value

    return {"feedback_input": feedback_input, "previous_attempt": previous_attempt}


def _feedback_input_text(state: ScreeningAgent) -> str:
    text = json.dumps(state["feedback_input"], indent=2)

    previous_attempt = state.get("previous_attempt")
    if previous_attempt:
        previous_input = dict(zip(previous_attempt["questions"].values(), previous_attempt["responses"]))
        text += (
            "\n\nPrevious attempt at these same questions (for comparison):\n"
            f"{json.dumps(previous_input, indent=2)}\n\n"
            "Previous feedback given:\n"
            f"{previous_attempt['feedback_output']}"
        )

    return text


def decider_agent(state: ScreeningAgent) -> dict:
    """Decides if the candidate cleared the interview"""
    job_description = state["job_description"]

    model = ChatAnthropic(model="claude-sonnet-4-5")
    model = model.with_structured_output(DecisionOutput, method="json_schema")

    response = model.invoke([
        SystemMessage(content=[{
            "type": "text",
            "text": f"{DECIDER_AGENT_PROMPT}: {job_description}"
        }]),
        HumanMessage(content=[{
            "type": "text",
            "text": _feedback_input_text(state),
            "cache_control": {"type": "ephemeral"}
        }])
    ])

    return {"result": response["result"]}


def feedback_agent(state: ScreeningAgent) -> dict:
    """Generate feedback for the user's answers"""
    model = ChatAnthropic(model="claude-sonnet-4-5")
    model = model.with_structured_output(FeedbackOutput, method="json_schema")

    response = model.invoke([
        SystemMessage(content=[{
            "type": "text",
            "text": FEEDBACK_AGENT_PROMPT
        }]),
        HumanMessage(content=[{
            "type": "text",
            "text": _feedback_input_text(state),
            "cache_control": {"type": "ephemeral"}
        }])
    ])

    return {"feedback_output": response["feedback"]}


async def present_results(state: ScreeningAgent, *, store: BaseStore) -> dict:
    """Persist the completed attempt to long-term memory, keyed by user + job description"""
    job_description = state["job_description"]
    namespace = memory_namespace(state["user_id"], job_description)

    attempt = {
        "job_description": job_description,
        "questions": state["questions"],
        "responses": state["responses"],
        "feedback_output": state["feedback_output"],
        "result": state["result"],
        "timestamp": time.time(),
    }

    await store.aput(namespace, str(uuid.uuid4()), attempt)

    choice = interrupt({
        "menu": ["practice_again", "exit"],
        "result": state["result"],
        "feedback_output": state["feedback_output"],
    })

    if choice == "practice_again":
        return {"menu_choice": choice, "responses": []}

    return {"menu_choice": choice}


def route_after_menu(state: ScreeningAgent) -> str:
    if state.get("menu_choice") == "practice_again":
        return "ask_questions"
    return END


# Graph Definition
graph = StateGraph(ScreeningAgent)

# add nodes
graph.add_node("generate_questions", generate_questions)
graph.add_node("ask_questions", ask_questions)
graph.add_node("compile_feedback_input", compile_feedback_input)
graph.add_node("feedback_agent", feedback_agent)
graph.add_node("decider_agent", decider_agent)
graph.add_node("present_results", present_results)

# add edges
graph.add_edge(START, "generate_questions")
graph.add_edge("generate_questions", "ask_questions")
graph.add_conditional_edges("ask_questions", should_continue_asking)

graph.add_edge("compile_feedback_input", "feedback_agent")
graph.add_edge("compile_feedback_input", "decider_agent")

graph.add_edge("feedback_agent", "present_results")
graph.add_edge("decider_agent", "present_results")
graph.add_conditional_edges("present_results", route_after_menu)

if __name__ == "__main__":
    from langgraph.store.memory import InMemoryStore

    compiled_graph = graph.compile(checkpointer=MemorySaver(), store=InMemoryStore())
    config = {"configurable": {"thread_id": "session-1"}}

    with get_usage_metadata_callback() as cb:
        result = compiled_graph.invoke({"job_description": JOB_DESCRIPTION}, config=config)

        while "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            answer = input(payload["question"])
            result = compiled_graph.invoke(Command(resume=answer), config=config)

        print(result["result"])
        print(result["feedback_output"])

    print()
    for model_name, usage in cb.usage_metadata.items():
        print(f"{model_name}")
        for key, value in usage.items():
            print(f"  {key:<28}: {value}")