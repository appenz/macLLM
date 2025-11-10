import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI()  # uses OPENAI_API_KEY

async def main():
    # Open a realtime WebSocket connection
    async with client.realtime.connect(model="gpt-realtime-mini") as conn:
        # Optional: update session config (only allowed fields)
        await conn.session.update(
            session={
                "type": "realtime",
                # Option 1: explicitly say we want text out:
                "output_modalities": ["text"],
                # (Some runtimes also support: "modalities": ["text"])
                "instructions": "Respond concisely.",
            }
        )

        # Add a user message to the conversation
        await conn.conversation.item.create(
            item={
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Explain quantum entanglement in one sentence.",
                    }
                ],
            }
        )

        # Ask the model to generate a response
        await conn.response.create()

        # Read and print streaming events
        async for event in conn:
            et = event.type

            if et == "response.output_text.delta":
                # incremental text
                print(event.delta, end="", flush=True)

            elif et == "response.output_text.done":
                # one text output finished -> newline
                print()

            elif et == "response.done":
                # complete response finished -> stop
                break

            elif et in ("error", "response.error"):
                # surface any issues
                print(f"\n[realtime error] {event}")
                break

asyncio.run(main())
