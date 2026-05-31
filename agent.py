import os
from dotenv import load_dotenv

from livekit.agents import (
    AgentSession,
    Agent,
    cli,
    JobContext,
    JobProcess,
    WorkerOptions,
    RoomInputOptions,
)
from livekit.plugins import openai, silero
from voice_prompt import VOICE_AGENT_INSTRUCTIONS

load_dotenv()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


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

    realtime_model = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-mini-realtime-preview-2024-12-17")
    model = openai.realtime.RealtimeModel(
        model=realtime_model,
        voice="alloy",
        temperature=0.6,
        modalities=["audio", "text"],
        turn_detection=None,
    )

    session = AgentSession(
        llm=model,
        vad=ctx.proc.userdata["vad"],
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
            prewarm_fnc=prewarm,
            agent_name="inshora-sarah",
        )
    )
