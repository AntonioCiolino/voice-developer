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
  const osc = ctx.createOscillator();
  const gainNode = ctx.createGain();

  osc.type = type;
  osc.frequency.setValueAtTime(freq, startTime);

  // Gentle attack and release envelope
  gainNode.gain.setValueAtTime(0, startTime);
  gainNode.gain.linearRampToValueAtTime(volume, startTime + 0.05);
  gainNode.gain.setValueAtTime(volume, startTime + duration - 0.1);
  gainNode.gain.linearRampToValueAtTime(0, startTime + duration);

  osc.connect(gainNode);
  gainNode.connect(masterGain);

  osc.start(startTime);
  osc.stop(startTime + duration + 0.05);
}

function playPad(ctx, masterGain, startTime, duration) {
  PAD_NOTES.forEach((freq) => {
    playNote(ctx, masterGain, freq, startTime, duration, 0.04, "sine");
    // Add a soft octave above
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
  const padTimerRef = useRef(null);
  const startedRef = useRef(false);

  const scheduleMelody = () => {
    const ctx = ctxRef.current;
    const masterGain = masterGainRef.current;
    if (!ctx || !masterGain) return;

    // Schedule notes slightly ahead of time (lookahead scheduling)
    const LOOKAHEAD = 0.3; // seconds
    const SCHEDULE_INTERVAL = 100; // ms

    const schedule = () => {
      while (nextNoteTimeRef.current < ctx.currentTime + LOOKAHEAD) {
        const { note, dur } = MELODY[melodyIndexRef.current % MELODY.length];
        const freq = PENTATONIC[note];
        playNote(ctx, masterGain, freq, nextNoteTimeRef.current, dur, 0.18, "triangle");

        // Every 4 notes, play a soft pad chord
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

    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    ctxRef.current = ctx;

    const masterGain = ctx.createGain();
    masterGain.gain.setValueAtTime(muted ? 0 : 1, ctx.currentTime);
    masterGain.connect(ctx.destination);
    masterGainRef.current = masterGain;

    nextNoteTimeRef.current = ctx.currentTime + 0.1;
    scheduleMelody();
  };

  const stop = () => {
    if (schedulerRef.current) clearTimeout(schedulerRef.current);
    if (ctxRef.current) {
      ctxRef.current.close();
      ctxRef.current = null;
    }
    startedRef.current = false;
  };

  // Start music on first user interaction (required by browsers)
  useEffect(() => {
    const handleInteraction = () => {
      start();
      window.removeEventListener("click", handleInteraction);
      window.removeEventListener("keydown", handleInteraction);
    };

    window.addEventListener("click", handleInteraction);
    window.addEventListener("keydown", handleInteraction);

    return () => {
      window.removeEventListener("click", handleInteraction);
      window.removeEventListener("keydown", handleInteraction);
      stop();
    };
  }, []);

  // Handle mute/unmute
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
