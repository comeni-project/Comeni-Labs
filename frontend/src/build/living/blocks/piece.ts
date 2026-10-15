/** `fastq@1.0.0` → `fastq 1.0.0`: the piece that read the file, as a person recognises it. One
 *  definition for the goal card and the upload card (issue 228). */
export const piece = (ref: string) => ref.replace("@", " ");
