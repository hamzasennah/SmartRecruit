import {
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Database,
  FileText,
  Files,
  Loader2,
  Play,
  RotateCcw,
  Search,
  Trophy,
  Upload,
} from "lucide-react";
import { ChangeEvent, FormEvent, InputHTMLAttributes, useMemo, useRef, useState } from "react";
import { SUPPORTED_EXTENSIONS, validateSelection } from "./validation";

type Evidence = {
  source: string;
  text: string;
  score: number;
  metadata: Record<string, string | number | boolean>;
};

type CategoryScore = {
  name: string;
  score: number;
  weight: number;
  weighted_score: number;
  matched: string[];
  missing: string[];
  evidence: Evidence[];
  details: Record<string, unknown>;
};

type CandidateMatch = {
  candidate_name: string | null;
  filename: string;
  final_score: number;
  category_scores: CategoryScore[];
  strengths: string[];
  weaknesses: string[];
  evidence: Evidence[];
};

type RankedCandidate = {
  rank: number;
  rank_label: string | null;
  is_tied: boolean;
  candidate: CandidateMatch;
};

type StructuredJob = {
  job_title: string | null;
  required_skills: {
    mandatory: string[];
    preferred: string[];
    soft: string[];
  };
  responsibilities: string[];
};

type RankingResponse = {
  job: StructuredJob;
  total_candidates: number;
  ranking: RankedCandidate[];
  errors: string[];
};

type AnalysisJobCreated = {
  analysis_id: string;
  status: string;
  status_url: string;
};

type AnalysisJobStatus = {
  analysis_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  result: RankingResponse | null;
  error: string | null;
};

type PipelineStep = {
  title: string;
  detail: string;
  target: number;
  icon: typeof Upload;
};

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const API_LABEL = API_URL || "proxy local /api -> 127.0.0.1:8002";
const API_KEY = import.meta.env.VITE_SMARTRECRUIT_API_KEY || "";
const ACCEPTED_EXTENSIONS = SUPPORTED_EXTENSIONS.join(",");

const PIPELINE_STEPS: PipelineStep[] = [
  {
    title: "Preparation",
    detail: "Validation des fichiers selectionnes",
    target: 12,
    icon: Files,
  },
  {
    title: "Upload",
    detail: "Transmission de la fiche et des CV",
    target: 28,
    icon: Upload,
  },
  {
    title: "Parsing",
    detail: "Extraction du texte et segmentation",
    target: 48,
    icon: FileText,
  },
  {
    title: "RAG",
    detail: "Embeddings NVIDIA, PostgreSQL et recherche semantique",
    target: 76,
    icon: Search,
  },
  {
    title: "Scoring",
    detail: "Matching explicable et classement final",
    target: 100,
    icon: BarChart3,
  },
];

function App() {
  const [jobFile, setJobFile] = useState<File | null>(null);
  const [cvFiles, setCvFiles] = useState<File[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<RankingResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const activeStep = useMemo(() => {
    return PIPELINE_STEPS.findIndex((step) => progress <= step.target);
  }, [progress]);

  const canAnalyze = Boolean(jobFile) && cvFiles.length > 0 && !isAnalyzing;

  function handleJobChange(event: ChangeEvent<HTMLInputElement>) {
    setJobFile(event.target.files?.[0] ?? null);
    setResult(null);
    setError(null);
  }

  function handleCvChange(event: ChangeEvent<HTMLInputElement>) {
    setCvFiles(Array.from(event.target.files ?? []));
    setResult(null);
    setError(null);
  }

  async function handleAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!jobFile || cvFiles.length === 0) {
      setError("Ajoutez une fiche de poste et au moins un CV.");
      return;
    }
    if (!API_KEY) {
      setError("Configurez VITE_SMARTRECRUIT_API_KEY pour lancer une analyse.");
      return;
    }
    const validationError = validateSelection(jobFile, cvFiles);
    if (validationError) {
      setError(validationError);
      return;
    }

    const formData = new FormData();
    formData.append("job_file", jobFile);
    cvFiles.forEach((file) => formData.append("cv_files", file));
    formData.append("top_k", "8");

    setIsAnalyzing(true);
    setResult(null);
    setError(null);
    setProgress(0);
    setAnalysisId(null);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_URL}/api/ranking/jobs`, {
        method: "POST",
        headers: { "X-API-Key": API_KEY },
        body: formData,
        signal: controller.signal,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(readApiError(payload, response.status));
      }
      const created = payload as AnalysisJobCreated;
      setAnalysisId(created.analysis_id);
      await pollAnalysis(created.analysis_id, controller.signal);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        setError("Analyse annulee.");
        setProgress(0);
      } else {
        setError(readNetworkError(caught));
        setProgress(0);
      }
    } finally {
      abortRef.current = null;
      setIsAnalyzing(false);
    }
  }

  async function pollAnalysis(id: string, signal: AbortSignal) {
    while (!signal.aborted) {
      const response = await fetch(`${API_URL}/api/ranking/jobs/${id}`, {
        headers: { "X-API-Key": API_KEY },
        signal,
      });
      const payload = (await response.json().catch(() => null)) as AnalysisJobStatus | null;
      if (!response.ok || !payload) {
        throw new Error(readApiError(payload, response.status));
      }
      setProgress(payload.progress);
      if (payload.status === "completed" && payload.result) {
        setResult(payload.result);
        return;
      }
      if (payload.status === "failed") {
        throw new Error(payload.error || "Analyse echouee.");
      }
      if (payload.status === "cancelled") {
        throw new DOMException("Analyse annulee.", "AbortError");
      }
      await sleep(900);
    }
  }

  async function cancelAnalysis() {
    abortRef.current?.abort();
    if (analysisId && API_KEY) {
      await fetch(`${API_URL}/api/ranking/jobs/${analysisId}`, {
        method: "DELETE",
        headers: { "X-API-Key": API_KEY },
      }).catch(() => null);
    }
    setIsAnalyzing(false);
    setProgress(0);
  }

  function resetForm() {
    setJobFile(null);
    setCvFiles([]);
    setResult(null);
    setError(null);
    setProgress(0);
    setAnalysisId(null);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SmartRecruit</p>
          <h1>Classement intelligent des CV</h1>
        </div>
        <div className="api-status">
          <Database size={17} />
          <span>{API_LABEL}</span>
        </div>
      </header>

      <section className="workspace-grid">
        <form className="input-panel" onSubmit={handleAnalyze}>
          <div className="panel-title">
            <FileText size={19} />
            <div>
              <h2>Documents</h2>
              <p>{cvFiles.length} CV selectionne(s)</p>
            </div>
          </div>

          <FilePicker
            title="Fiche de poste"
            icon={FileText}
            fileNames={jobFile ? [jobFile.name] : []}
            inputProps={{
              accept: ACCEPTED_EXTENSIONS,
              onChange: handleJobChange,
            }}
          />

          <FilePicker
            title="CV candidats"
            icon={Files}
            fileNames={cvFiles.map((file) => file.name)}
            inputProps={{
              accept: ACCEPTED_EXTENSIONS,
              multiple: true,
              onChange: handleCvChange,
            }}
          />

          <div className="actions">
            <button className="primary-button" disabled={!canAnalyze} type="submit">
              {isAnalyzing ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
              Analyser
            </button>
            <button className="ghost-button" type="button" onClick={isAnalyzing ? cancelAnalysis : resetForm}>
              <RotateCcw size={18} />
              {isAnalyzing ? "Annuler" : "Reinitialiser"}
            </button>
          </div>
        </form>

        <section className="process-panel">
          <div className="panel-title">
            <BrainCircuit size={20} />
            <div>
              <h2>Pipeline</h2>
              <p>{isAnalyzing ? "Analyse en cours" : result ? "Analyse terminee" : "Pret"}</p>
            </div>
          </div>

          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="progress-meta">
            <span>{Math.round(progress)}%</span>
            <span>{result ? `${result.total_candidates} candidat(s) analyses` : "En attente"}</span>
          </div>

          <div className="steps-grid">
            {PIPELINE_STEPS.map((step, index) => {
              const Icon = step.icon;
              const complete = progress >= step.target;
              const active = isAnalyzing && index === activeStep;
              return (
                <article className={`step-card ${complete ? "complete" : ""} ${active ? "active" : ""}`} key={step.title}>
                  <div className="step-icon">{complete ? <CheckCircle2 size={18} /> : <Icon size={18} />}</div>
                  <div>
                    <h3>{step.title}</h3>
                    <p>{step.detail}</p>
                  </div>
                </article>
              );
            })}
          </div>

          {error && (
            <div className="error-box">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          )}
        </section>
      </section>

      {result && <ResultsView response={result} />}
    </main>
  );
}

type FilePickerProps = {
  title: string;
  icon: typeof Upload;
  fileNames: string[];
  inputProps: InputHTMLAttributes<HTMLInputElement>;
};

function FilePicker({ title, icon: Icon, fileNames, inputProps }: FilePickerProps) {
  return (
    <section className="file-picker">
      <div className="file-picker-head">
        <Icon size={18} />
        <h3>{title}</h3>
      </div>
      <label className="file-input">
        <Upload size={17} />
        <span>Choisir</span>
        <input type="file" {...inputProps} />
      </label>
      <div className="file-list">
        {fileNames.length === 0 ? (
          <span className="muted">Aucun fichier</span>
        ) : (
          fileNames.map((name) => (
            <span className="file-chip" key={name}>
              {name}
            </span>
          ))
        )}
      </div>
    </section>
  );
}

function ResultsView({ response }: { response: RankingResponse }) {
  const best = response.ranking[0]?.candidate;
  return (
    <section className="results-stack">
      <div className="summary-grid">
        <MetricCard label="Candidats" value={String(response.total_candidates)} />
        <MetricCard label="Meilleur score" value={best ? formatScore(best.final_score) : "0%"} />
        <MetricCard label="Erreurs" value={String(response.errors.length)} tone={response.errors.length ? "warn" : "ok"} />
      </div>

      <CriteriaPanel job={response.job} />

      {response.errors.length > 0 && (
        <section className="result-card warning-card">
          <h2>Erreurs de traitement</h2>
          <ul>
            {response.errors.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="result-card">
        <div className="result-title">
          <Trophy size={22} />
          <h2>Classement final</h2>
        </div>
        <div className="ranking-table">
          <div className="ranking-row ranking-head">
            <span>Rang</span>
            <span>Candidat</span>
            <span>Score</span>
            <span>Forces</span>
            <span>Faiblesses</span>
          </div>
          {response.ranking.map((item) => (
            <div className="ranking-row" key={`${item.rank}-${item.candidate.filename}`}>
              <strong className="rank-value ranking-rank">{item.rank_label || item.rank}</strong>
              <div className="ranking-candidate">
                <strong>{item.candidate.candidate_name || "Candidat non precise"}</strong>
                <span className="filename">{item.candidate.filename}</span>
              </div>
              <div className="ranking-score">
                <ScoreBadge score={item.candidate.final_score} />
              </div>
              <div className="ranking-list">
                <TextList values={item.candidate.strengths} />
              </div>
              <div className="ranking-list">
                <TextList values={item.candidate.weaknesses} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="candidate-grid">
        {response.ranking.map((item) => (
          <CandidateCard item={item} key={item.candidate.filename} />
        ))}
      </section>
    </section>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" }) {
  return (
    <article className={`metric-card ${tone || ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function CriteriaPanel({ job }: { job: StructuredJob }) {
  return (
    <section className="result-card">
      <h2>Fiche de poste</h2>
      <p className="job-title">{job.job_title || "Poste non precise"}</p>
      <div className="criteria-grid">
        <CriteriaList title="Obligatoires" values={job.required_skills.mandatory} />
        <CriteriaList title="Souhaitees" values={job.required_skills.preferred} />
        <CriteriaList title="Soft skills" values={job.required_skills.soft} />
        <CriteriaList title="Responsabilites" values={job.responsibilities} />
      </div>
    </section>
  );
}

function CriteriaList({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="criteria-list">
      <h3>{title}</h3>
      {values.length === 0 ? (
        <span className="muted">Non renseigne</span>
      ) : (
        <ul>
          {values.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CandidateCard({ item }: { item: RankedCandidate }) {
  const candidate = item.candidate;
  return (
    <article className="candidate-card">
      <div className="candidate-head">
        <div>
          <span className="rank-mini">{item.rank_label || item.rank}</span>
          <h2>{candidate.candidate_name || "Candidat non precise"}</h2>
          <p>{candidate.filename}</p>
        </div>
        <ScoreBadge score={candidate.final_score} />
      </div>

      <div className="split">
        <div>
          <h3>Forces</h3>
          <TextList values={candidate.strengths} />
        </div>
        <div>
          <h3>Faiblesses</h3>
          <TextList values={candidate.weaknesses} />
        </div>
      </div>

      <div className="category-stack">
        {candidate.category_scores.map((category) => (
          <CategoryBlock category={category} key={category.name} />
        ))}
      </div>

      {candidate.evidence.length > 0 && (
        <details className="evidence-details">
          <summary>Preuves principales</summary>
          <ul>
            {candidate.evidence.slice(0, 6).map((evidence, index) => (
              <li key={`${evidence.source}-${index}`}>
                <span className="evidence-source">{evidence.source}</span>
                <span className="evidence-score">{evidence.score.toFixed(3)}</span>
                <p>{evidence.text}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

function CategoryBlock({ category }: { category: CategoryScore }) {
  const partialSkills =
    category.name === "technical_skills"
      ? [
          ...formatPartialSkillMatches(category.details?.partial_mandatory),
          ...formatPartialSkillMatches(category.details?.partial_preferred),
        ]
      : [];
  const partialResponsibilities =
    category.name === "responsibilities"
      ? formatPartialResponsibilities(category.details?.partial, category.details?.responsibility_scores)
      : [];

  return (
    <section className="category-block">
      <div className="category-title">
        <h3>{category.name}</h3>
        <strong>{formatScore(category.score)}</strong>
      </div>
      <div className="score-line">
        <span style={{ width: `${Math.max(0, Math.min(category.score, 100))}%` }} />
      </div>
      <div className="split compact">
        <div>
          <h4>Correspondances</h4>
          <TextList values={category.matched} empty="Aucune" />
        </div>
        <div>
          <h4>Manquants</h4>
          <TextList values={category.missing} empty="Aucun" />
        </div>
      </div>
      {partialSkills.length > 0 && (
        <div className="partial-skills">
          <h4>Correspondances partielles</h4>
          <TextList values={partialSkills} empty="Aucune" />
        </div>
      )}
      {partialResponsibilities.length > 0 && (
        <div className="partial-skills">
          <h4>Responsabilites partiellement prouvees</h4>
          <TextList values={partialResponsibilities} empty="Aucune" />
        </div>
      )}
      {Object.keys(category.details || {}).length > 0 && (
        <details className="detail-json">
          <summary>Details</summary>
          <dl>
            {Object.entries(category.details).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{formatDetail(value)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </section>
  );
}

function formatPartialResponsibilities(partial: unknown, responsibilityScores: unknown): string[] {
  const labels: string[] = [];
  if (Array.isArray(responsibilityScores)) {
    responsibilityScores.forEach((item) => {
      if (!item || typeof item !== "object") {
        return;
      }
      const record = item as Record<string, unknown>;
      if (String(record.status || "") !== "partial") {
        return;
      }
      const responsibility = String(record.responsibility || "").trim();
      const score = Number(record.score);
      if (responsibility) {
        labels.push(Number.isFinite(score) ? `${responsibility} (${score.toFixed(0)}%)` : responsibility);
      }
    });
  }
  if (labels.length === 0 && Array.isArray(partial)) {
    partial.forEach((item) => {
      const label = String(item || "").trim();
      if (label) {
        labels.push(label);
      }
    });
  }
  return Array.from(new Set(labels));
}

function formatPartialSkillMatches(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      if (!item || typeof item !== "object") {
        return "";
      }
      const record = item as Record<string, unknown>;
      const skill = String(record.skill || "").trim();
      const evidence = String(record.evidence || "").trim();
      const credit = Number(record.credit_percent);
      const creditLabel = Number.isFinite(credit) ? `, credit ${credit.toFixed(0)}%` : "";
      if (skill && evidence) {
        return `${skill} via ${evidence}${creditLabel}`;
      }
      return skill;
    })
    .filter(Boolean);
}

function ScoreBadge({ score }: { score: number }) {
  const tone = score >= 70 ? "high" : score >= 40 ? "medium" : "low";
  return <strong className={`score-badge ${tone}`}>{formatScore(score)}</strong>;
}

function TextList({ values, empty = "Aucun" }: { values: string[]; empty?: string }) {
  if (!values || values.length === 0) {
    return <span className="muted">{empty}</span>;
  }
  return (
    <ul className="text-list">
      {values.map((value) => (
        <li key={value}>{value}</li>
      ))}
    </ul>
  );
}

function formatScore(value: number) {
  return `${value.toFixed(2)}%`;
}

function formatDetail(value: unknown) {
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "Aucun";
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value ?? "null");
}

function readApiError(payload: unknown, status: number) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }
  return `Erreur API ${status}`;
}

function readNetworkError(caught: unknown) {
  if (caught instanceof TypeError && caught.message.toLowerCase().includes("fetch")) {
    return "API inaccessible. Verifiez que FastAPI est lance sur http://127.0.0.1:8002, puis rechargez la page.";
  }
  return caught instanceof Error ? caught.message : "Erreur inconnue pendant l'analyse.";
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default App;
