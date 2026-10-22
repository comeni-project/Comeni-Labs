/** **Where a pipeline opens** (issue 390): its conversation, when it has one; otherwise its draft,
 *  which `BuildRoute` opens a conversation for (#395). Home and the jump dialog link through this. */
export function pipelineAddress(pipeline: { id: string; session?: string | null }): string {
  return pipeline.session
    ? `/build?session=${encodeURIComponent(pipeline.session)}`
    : `/build?draft=${encodeURIComponent(pipeline.id)}`;
}
