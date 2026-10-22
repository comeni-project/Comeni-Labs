/** **Where a pipeline opens** (issue 390): in the conversation it was built in, when there is one,
 *  and on the canvas when it was drawn by hand. Home and the jump dialog both link through this. */
export function pipelineAddress(pipeline: { id: string; session?: string | null }): string {
  return pipeline.session
    ? `/build?session=${encodeURIComponent(pipeline.session)}`
    : `/build?draft=${encodeURIComponent(pipeline.id)}`;
}
