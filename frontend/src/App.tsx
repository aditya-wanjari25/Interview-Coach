import { useRef, useState } from "react";
import VoiceOrb from "./VoiceOrb";
import {
  startInterview,
  submitAnswer,
  fetchSpeechAudioUrl,
  type AnswerResponse,
} from "./api";
import "./App.css";

type Phase = "setup" | "question" | "menu" | "done";
type AnswerMode = "choose" | "typing" | "listening" | "reviewSpoken";

function App() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [userId, setUserId] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [menu, setMenu] = useState<string[]>([]);
  const [result, setResult] = useState<boolean | undefined>();
  const [feedback, setFeedback] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [answerMode, setAnswerMode] = useState<AnswerMode>("choose");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [transcript, setTranscript] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const speechSupported =
    typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition) != null;

  async function playQuestion(text: string) {
    try {
      const url = await fetchSpeechAudioUrl(text);
      const audio = audioRef.current;
      if (!audio) return;
      audio.src = url;
      await audio.play();
    } catch {
      // TTS is a nice-to-have; if it fails, the question text is still on screen.
      setErrorMsg("Couldn't play audio for this question, but you can still answer below.");
    }
  }

  function handleGraphResponse(res: AnswerResponse) {
    setErrorMsg(null);
    if (res.status === "in_progress") {
      setPhase("question");
      setAnswerMode("choose");
      setTypedAnswer("");
      setTranscript("");
      setQuestion(res.question ?? "");
      playQuestion(res.question ?? "");
    } else if (res.status === "awaiting_menu_choice") {
      setPhase("menu");
      setMenu(res.menu ?? []);
      setResult(res.result);
      setFeedback(res.feedback_output ?? "");
    } else {
      setPhase("done");
      setResult(res.result);
      setFeedback(res.feedback_output ?? "");
    }
  }

  async function handleStart(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrorMsg(null);
    try {
      const res = await startInterview(jobDescription, userId);
      setSessionId(res.session_id);
      setPhase("question");
      setAnswerMode("choose");
      setQuestion(res.question);
      await playQuestion(res.question);
    } catch {
      setErrorMsg("Couldn't start the interview. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  async function sendAnswer(answer: string) {
    if (!sessionId || !answer.trim()) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const res = await submitAnswer(sessionId, answer);
      handleGraphResponse(res);
    } catch {
      setErrorMsg("Couldn't submit that answer. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function startListening() {
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Ctor) return;

    const recognition = new Ctor();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;

    let finalTranscript = "";

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += chunk + " ";
        } else {
          interim += chunk;
        }
      }
      setTranscript((finalTranscript + interim).trim());
    };

    recognition.onerror = () => {
      setErrorMsg("Speech recognition failed. Try typing your answer instead.");
      setAnswerMode("choose");
    };

    recognition.onend = () => {
      setAnswerMode((mode) => (mode === "listening" ? "reviewSpoken" : mode));
    };

    recognitionRef.current = recognition;
    setTranscript("");
    setAnswerMode("listening");
    recognition.start();
  }

  function stopListening() {
    recognitionRef.current?.stop();
  }

  return (
    <div className="app">
      <audio
        ref={audioRef}
        onPlay={() => setSpeaking(true)}
        onEnded={() => setSpeaking(false)}
        onPause={() => setSpeaking(false)}
      />

      <VoiceOrb speaking={speaking} />

      {errorMsg && <p className="error">{errorMsg}</p>}

      {phase === "setup" && (
        <form className="panel" onSubmit={handleStart}>
          <h1>Interview Coach</h1>
          <label>
            Your name or email
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </label>
          <label>
            Job description
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              rows={8}
              placeholder="Paste the job description here..."
              required
            />
          </label>
          <button type="submit" disabled={busy}>
            {busy ? "Starting..." : "Start Interview"}
          </button>
        </form>
      )}

      {phase === "question" && (
        <div className="panel">
          <p className="question">{question}</p>

          {answerMode === "choose" && (
            <div className="choice-row">
              <button onClick={() => setAnswerMode("typing")} disabled={busy}>
                Type Answer
              </button>
              <button
                onClick={startListening}
                disabled={busy || !speechSupported}
                title={speechSupported ? "" : "Speech recognition isn't supported in this browser"}
              >
                Speak Answer
              </button>
            </div>
          )}

          {answerMode === "typing" && (
            <div className="answer-block">
              <textarea
                value={typedAnswer}
                onChange={(e) => setTypedAnswer(e.target.value)}
                rows={5}
                placeholder="Type your answer..."
                autoFocus
              />
              <button onClick={() => sendAnswer(typedAnswer)} disabled={busy || !typedAnswer.trim()}>
                Submit
              </button>
            </div>
          )}

          {answerMode === "listening" && (
            <div className="answer-block">
              <p className="transcript listening">Listening... {transcript}</p>
              <button onClick={stopListening}>Done Speaking</button>
            </div>
          )}

          {answerMode === "reviewSpoken" && (
            <div className="answer-block">
              <textarea
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                rows={5}
              />
              <div className="choice-row">
                <button onClick={() => sendAnswer(transcript)} disabled={busy || !transcript.trim()}>
                  Submit
                </button>
                <button onClick={startListening} disabled={busy}>
                  Re-record
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {phase === "menu" && (
        <div className="panel">
          <h2>{result ? "You passed this round" : "Not quite there yet"}</h2>
          <pre className="feedback">{feedback}</pre>
          <div className="choice-row">
            {menu.map((choice) => (
              <button key={choice} onClick={() => sendAnswer(choice)} disabled={busy}>
                {choice === "practice_again" ? "Practice Again" : "Exit"}
              </button>
            ))}
          </div>
        </div>
      )}

      {phase === "done" && (
        <div className="panel">
          <h2>{result ? "You passed this round" : "Not quite there yet"}</h2>
          <pre className="feedback">{feedback}</pre>
          <button
            onClick={() => {
              setPhase("setup");
              setSessionId(null);
            }}
          >
            Start New Interview
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
