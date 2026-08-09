import { z } from 'zod'

const feedbackResponseSchema = z.object({
  id: z.string().min(1),
  userId: z.string().min(1),
  videoId: z.string().nullable().optional(),
  targetType: z.enum(['search_result', 'video_answer', 'chapter', 'subtitle', 'video_metadata']),
  targetId: z.string().min(1),
  feedbackType: z.enum(['helpful', 'not_relevant', 'correction']),
  content: z.string().nullable().optional(),
  status: z.string().min(1),
})

export interface FeedbackPayload {
  videoId?: string
  targetType: 'search_result' | 'video_answer' | 'chapter' | 'subtitle'
  targetId: string
  feedbackType: 'helpful' | 'not_relevant' | 'correction'
  content?: string
}

export async function submitFeedback(payload: FeedbackPayload): Promise<void> {
  const response = await fetch('/api/v1/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      videoId: payload.videoId,
      targetType: payload.targetType,
      targetId: payload.targetId,
      feedbackType: payload.feedbackType,
      content: payload.content,
    }),
  })
  if (!response.ok) throw new Error('反馈提交失败')
  feedbackResponseSchema.parse(await response.json())
}
