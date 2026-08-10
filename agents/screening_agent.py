from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END, MessagesState
from typing_extensions import TypedDict
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage
from job_description import JOB_DESCRIPTION
from dotenv import load_dotenv
import json
load_dotenv()

'''
Screening Graph:
Start -> Generate Questions -> Ask Questions , Feedback -> End
Generate Questions:
    - Generate 5 questions for the user to answer
    - Return the questions in a list
Ask Questions (Interviewier Agent):
    - Ask the questions to the user
    - Save answers in short term memory
    - Ask the next question

Feedback Agent:
    - Runs parallel to the Ask Questions agent
    - Generates feedback as the user answers the questions
    - Saves the feedback in short term memory along with question and answer.
    - Returns a rationale for the pass/fail decision
    - Returns a pass/fail decision
End:
    - Returns the pass/fail rationale
    - Returns the pass/fail decision

'''
class QuestionFormat(TypedDict):
    question1: str
    question2: str
    question3: str
    question4: str
    question5: str

class FeedbackOutput(TypedDict):
    result_reason: str
    result: bool


class ScreeningAgent(TypedDict):
    result: bool #the result of the screening
    questions: QuestionFormat #the questions to ask the user
    job_description: str #the job description
    responses: list
    feedback_input: dict
    feedback_output: str




def generate_questions(state: ScreeningAgent) -> QuestionFormat:
    """Generate questions for the user to answer"""
    model = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.0,
       
    )
    model = model.with_structured_output(QuestionFormat, method="json_schema")

    response = model.invoke(
        [
            SystemMessage(content="You are a helpful assistant that generates 5 questions for an initial screening interview."),
            HumanMessage(content=f"Generate questions for the user to answer based on the following job description: {state['job_description']}")
        ]
    )
    
    return {"questions": response}

def ask_questions(state: ScreeningAgent) -> ScreeningAgent:
    """Ask the questions to the user"""
    questions = state["questions"]
    responses = state.get("responses", [])    
    
    # find out which question we are now
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
    return "feedback_agent"


def feedback_agent(state: ScreeningAgent) -> ScreeningAgent:
    """Generate feedback for the user's answers"""
    questions = state["questions"]
    responses = state["responses"]
    job_description = state["job_description"]
    feedback_input = {}
    for i, key in enumerate(questions):
        feedback_input[questions[key]] = responses[i]
    
    model = ChatAnthropic(
        model = "claude-sonnet-4-5",
    )
    model = model.with_structured_output(FeedbackOutput, method = "json_schema")
    response = model.invoke([
        SystemMessage(content=f"You are a skilled interviewer tasked with judging an initial screening call. Decide based on user responses if the candidate clears this round. Provide a rationale and a final result (Pass: True / Fail: False) Here is the job description {job_description}"),
        HumanMessage(content=json.dumps(feedback_input, indent=2))]
    )

    return {"result": response["result"], "feedback_output":response["result_reason"] }


# Graph Definition
graph = StateGraph(ScreeningAgent)

# add nodes
graph.add_node("generate_questions", generate_questions)
graph.add_node("ask_questions", ask_questions)
graph.add_node("feedback_agent",feedback_agent )

# add edges
graph.add_edge(START, "generate_questions")
graph.add_edge("generate_questions","ask_questions")
graph.add_conditional_edges("ask_questions", should_continue_asking)
graph.add_edge("feedback_agent", END)

# compile
checkpointer = MemorySaver()
compiled_graph = graph.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "session-1"}}

result = compiled_graph.invoke({"job_description": JOB_DESCRIPTION}, config=config)

# keep resuming until there's no more interrupt
while "__interrupt__" in result:
    payload = result["__interrupt__"][0].value
    answer = input(payload["question"])
    result = compiled_graph.invoke(Command(resume=answer), config=config)

print(result["result"])
print(result["feedback_output"])