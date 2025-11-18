from src.supervisor import app


def main():
    result = app.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": input("enter your query: "),
                }
            ]
        },
        config={"run": True}   
    )

    for m in result["messages"]:
        m.pretty_print()



if __name__ == "__main__":
    main()
