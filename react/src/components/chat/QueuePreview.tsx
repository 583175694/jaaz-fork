import { GenerationJob } from '@/types/types'

type QueuePreviewProps = {
  jobs: GenerationJob[]
}

const QueuePreview: React.FC<QueuePreviewProps> = ({ jobs }) => {
  if (jobs.length === 0) {
    return null
  }

  const runningJob = jobs.find((job) => job.status === 'running') || null
  const queuedJobs = jobs.filter((job) => job.status === 'queued').slice(0, 3)

  if (!runningJob && queuedJobs.length === 0) {
    return null
  }

  return (
    <div className="rounded-xl border border-primary/15 bg-background/90 px-3 py-2">
      <div className="flex flex-col gap-1 text-sm text-muted-foreground">
        {runningJob ? (
          <div>
            正在生成：
            <span className="ml-1 text-foreground">
              {runningJob.summary_text || runningJob.type}
            </span>
          </div>
        ) : null}

        {queuedJobs.map((job) => (
          <div key={job.id}>
            接下来：
            <span className="ml-1 text-foreground">
              {job.summary_text || job.type}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default QueuePreview
