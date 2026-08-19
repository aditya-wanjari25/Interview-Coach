import type { JobSummary } from "./api";

interface JobsListProps {
  jobs: JobSummary[];
  loading: boolean;
  onSelectJob: (jdHash: string) => void;
  onNewInterview: () => void;
  onLogout: () => void;
}

export default function JobsList({
  jobs,
  loading,
  onSelectJob,
  onNewInterview,
  onLogout,
}: JobsListProps) {
  return (
    <div className="panel">
      <div className="row-between">
        <h1>Your Practice History</h1>
        <button className="ghost" onClick={onLogout}>
          Log out
        </button>
      </div>

      <button onClick={onNewInterview}>Start New Interview</button>

      {loading && <p>Loading...</p>}
      {!loading && jobs.length === 0 && (
        <p>No practice sessions yet. Start one above.</p>
      )}

      <ul className="job-list">
        {jobs.map((job) => (
          <li key={job.jd_hash} className="job-item" onClick={() => onSelectJob(job.jd_hash)}>
            <p className="job-desc">
              {job.job_description.length > 140
                ? job.job_description.slice(0, 140) + "..."
                : job.job_description}
            </p>
            <div className="job-meta">
              <span>
                {job.attempt_count} attempt{job.attempt_count !== 1 ? "s" : ""}
              </span>
              <span className={`badge ${job.last_result ? "pass" : "fail"}`}>
                {job.last_result ? "Passed" : "Not yet"}
              </span>
              <span>{new Date(job.last_attempt_at * 1000).toLocaleDateString()}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
