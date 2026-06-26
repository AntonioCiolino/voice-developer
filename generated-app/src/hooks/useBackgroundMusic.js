import { useEffect, useRef, useState } from "react";

// Pentatonic scale notes (C major pentatonic) in Hz
const PENTATONIC = [261.63, 293.66, 329.63, 392.0, 440.0, 523.25, 587.33, 659.25, 783.99, 880.0];

// A calm, looping melody pattern using indices into PENTATONIC
const MELODY = [
  { note: 4, dur: 0.6 },
  { note: 5, dur: 0.4 },
  { note: 6, dur: 0.6 },
  { note: 4, dur: 0.4 },
  { note: 3, dur: 0.8 },
  { note: 2, dur: 0.4 },
  { note: 3, dur: 0.6 },
  { note: 1, dur: 0.4 },
  { note: 2, dur: 0.8 },
  { note: 0, dur: 0.4 },
  { note: 2, dur: 0.6 },
  { note: 3, dur: 0.4 },
  { note: 4, dur: 1.0 },
  { note: 5, dur: 0.4 },
  { note: 6, dur: 0.6 },
  { note: 5, dur: 0.4 },
  { note: 4, dur: 0.6 },
  { note: 3, dur: 0.4 },
  { note: 5, dur: 0.8 },
  { note: 4, dur: 0.6 },
];

// Gentle pad/chord notes played softly underneath
const PAD_NOTES = [261.63, 329.63, 392.0]; // C, E, G

function playNote(ctx, masterGain, freq, startTime, duration, volume = 0.18, type = "triangle") {
  try {
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, startTime);

    gainNode.gain.setValueAtTime(0, startTime);
    gainNode.gain.linearRampToValueAtTime(volume, startTime + 0.05);
    gainNode.gain.setValueAtTime(volume, startTime + duration - 0.1);
    gainNode.gain.linearRampToValueAtTime(0, startTime + duration);

    osc.connect(gainNode);
    gainNode.connect(masterGain);

    osc.start(startTime);
    osc.stop(startTime + duration + 0.05);
  } catch (e) {
    // Silently ignore audio errors on iOS
  }
}

function playPad(ctx, masterGain, startTime, duration) {
  PAD_NOTES.forEach((freq) => {
    playNote(ctx, masterGain, freq, startTime, duration, 0.04, "sine");
    playNote(ctx, masterGain, freq * 2, startTime, duration, 0.02, "sine");
  });
}

export function useBackgroundMusic() {
  const [muted, setMuted] = useState(false);
  const ctxRef = useRef(null);
  const masterGainRef = useRef(null);
  const schedulerRef = useRef(null);
  const nextNoteTimeRef = useRef(0);
  const melodyIndexRef = useRef(0);
  const startedRef = useRef(false);
  const mutedRef = useRef(false);

  // Keep mutedRef in sync so the resume handler can read current value
  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);

  const scheduleMelody = () => {
    const ctx = ctxRef.current;
    const masterGain = masterGainRef.current;
    if (!ctx || !masterGain) return;

    const LOOKAHEAD = 0.3;
    const SCHEDULE_INTERVAL = 100;

    const schedule = () => {
      const ctx = ctxRef.current;
      const masterGain = masterGainRef.current;
      if (!ctx || !masterGain) return;

      // iOS may suspend the context — try to resume it
      if (ctx.state === "suspended") {
        ctx.resume().catch(() => {});
      }

      while (nextNoteTimeRef.current < ctx.currentTime + LOOKAHEAD) {
        const { note, dur } = MELODY[melodyIndexRef.current % MELODY.length];
        const freq = PENTATONIC[note];
        playNote(ctx, masterGain, freq, nextNoteTimeRef.current, dur, 0.18, "triangle");

        if (melodyIndexRef.current % 4 === 0) {
          playPad(ctx, masterGain, nextNoteTimeRef.current, dur * 3.5);
        }

        nextNoteTimeRef.current += dur;
        melodyIndexRef.current = (melodyIndexRef.current + 1) % MELODY.length;
      }

      schedulerRef.current = setTimeout(schedule, SCHEDULE_INTERVAL);
    };

    schedule();
  };

  const start = () => {
    if (startedRef.current) return;
    startedRef.current = true;

    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;

      const ctx = new AudioCtx();
      ctxRef.current = ctx;

      const masterGain = ctx.createGain();
      masterGain.gain.setValueAtTime(mutedRef.current ? 0 : 1, ctx.currentTime);
      masterGain.connect(ctx.destination);
      masterGainRef.current = masterGain;

      // iOS often starts context in suspended state — resume immediately
      if (ctx.state === "suspended") {
        ctx.resume().then(() => {
          nextNoteTimeRef.current = ctx.currentTime + 0.1;
          scheduleMelody();
        }).catch(() => {});
      } else {
        nextNoteTimeRef.current = ctx.currentTime + 0.1;
        scheduleMelody();
      }
    } catch (e) {
      // Audio not supported
    }
  };

  const stop = () => {
    if (schedulerRef.current) clearTimeout(schedulerRef.current);
    if (ctxRef.current) {
      try {
        ctxRef.current.close();
      } catch (e) {}
      ctxRef.current = null;
    }
    startedRef.current = false;
  };

  // Resume context on any touch/click (iOS requires this)
  const resumeCtx = () => {
    if (ctxRef.current && ctxRef.current.state === "suspended") {
      ctxRef.current.resume().catch(() => {});
    }
  };

  useEffect(() => {
    const handleInteraction = () => {
      start();
      resumeCtx();
    };

    // Use both touchstart and click for iOS compatibility
    window.addEventListener("touchstart", handleInteraction, { passive: true });
    window.addEventListener("click", handleInteraction);
    window.addEventListener("keydown", handleInteraction);

    // Also resume on any subsequent touch (iOS can re-suspend)
    window.addEventListener("touchstart", resumeCtx, { passive: true });

    return () => {
      window.removeEventListener("touchstart", handleInteraction);
      window.removeEventListener("click", handleInteraction);
      window.removeEventListener("keydown", handleInteraction);
      window.removeEventListener("touchstart", resumeCtx);
      stop();
    };
  }, []);

  useEffect(() => {
    if (masterGainRef.current && ctxRef.current) {
      masterGainRef.current.gain.setTargetAtTime(
        muted ? 0 : 1,
        ctxRef.current.currentTime,
        0.1
      );
    }
  }, [muted]);

  const toggleMute = () => setMuted((m) => !m);

  return { muted, toggleMute };
}
