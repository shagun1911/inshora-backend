import os
from dotenv import load_dotenv

from livekit.agents import AgentSession, Agent, cli, JobContext, WorkerOptions, RoomInputOptions
from livekit.plugins import openai, silero
from voice_prompt import VOICE_AGENT_INSTRUCTIONS

load_dotenv()


class Sarah(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=VOICE_AGENT_INSTRUCTIONS)

    async def on_enter(self):
        await self.session.say(
            "Hi, I'm Sarah with Inshora Group. What insurance question can I help with today?",
            allow_interruptions=True,
        )


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    chat_model = os.getenv("CHAT_MODEL", "gpt-4o-mini")

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=openai.STT(model="gpt-4o-mini-transcribe"),
        llm=openai.LLM(model=chat_model),
        tts=openai.TTS(model="tts-1", voice="alloy"),
    )

    await session.start(
        agent=Sarah(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            pre_connect_audio=True,
            pre_connect_audio_timeout=15.0,
        ),
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="inshora-sarah",
        )
    )
