from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END, MessagesState
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from job_description import JOB_DESCRIPTION
from dotenv import load_dotenv

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

class ScreeningAgent(TypedDict):
    messages: MessagesState #all the messages in the conversation
    result: bool #the result of the screening
    questions: QuestionFormat #the questions to ask the user
    job_description: str #the job description




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

def feedback_agent(state: ScreeningAgent) -> ScreeningAgent:
    """Generate feedback for the user's answers"""


# Graph Definition
graph = StateGraph(ScreeningAgent)

# add nodes
graph.add_node("generate_questions", generate_questions)

# add edges
graph.add_edge(START, "generate_questions")
graph.add_edge("generate_questions", END)

# compile
compiled_graph = graph.compile()


# run the graph
result = compiled_graph.invoke({
    "job_description": JOB_DESCRIPTION
})

print(result["questions"])

    