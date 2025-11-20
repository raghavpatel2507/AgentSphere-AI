from src.core.agents.supervisor import app
from src.core.agents.callbacks import AgentCallbackHandler


def main():
    agent_callback = AgentCallbackHandler()
    result = app.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": input("enter your query: "),
                }
            ]
        },
        config={"run": True, "callbacks": [agent_callback]}   
    )

    # Get the last message which should be the final answer
    # last_message = result["messages"][-1]
    # print(f"\n\033[1;36m🤖 Final Answer:\033[0m\n{last_message.content}\n")
    for m in result["messages"]:
        m.pretty_print()



if __name__ == "__main__":
    main()
