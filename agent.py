import os
from dotenv import load_dotenv
from openai.types import realtime

from livekit.agents import AgentSession, Agent, cli, JobContext, WorkerOptions, RoomInputOptions
from livekit.plugins import openai
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

    realtime_model = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-mini-realtime-preview-2024-12-17")
    model = openai.realtime.RealtimeModel(
        model=realtime_model,
        voice="alloy",
        temperature=0.6,
        input_audio_transcription=realtime.AudioTranscription(
            model="gpt-4o-mini-transcribe",
            language="en",
        ),
        turn_detection=realtime.realtime_audio_input_turn_detection.ServerVad(
            type="server_vad",
            threshold=0.45,
            prefix_padding_ms=400,
            silence_duration_ms=900,
            create_response=True,
        ),
    )

    tts = openai.TTS(model="tts-1", voice="alloy")

    session = AgentSession(llm=model, tts=tts)

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
