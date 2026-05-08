/** Shared Gemini generation. Text + image, used by all pipelines. */

export async function generateText(prompt: string): Promise<string | null> {
  const key = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY
  if (!key) return null

  const { GoogleGenAI } = await import('@google/genai')
  const client = new GoogleGenAI({ apiKey: key })

  const response = await client.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: [{ role: 'user', parts: [{ text: prompt }] }],
  })

  return response.candidates?.[0]?.content?.parts?.[0]?.text?.trim() ?? null
}

export async function generateImage(prompt: string): Promise<Buffer | null> {
  const key = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY
  if (!key) return null

  const { GoogleGenAI } = await import('@google/genai')
  const client = new GoogleGenAI({ apiKey: key })

  const response = await client.models.generateContent({
    model: 'gemini-3.1-flash-image-preview',
    contents: [{ role: 'user', parts: [{ text: prompt }] }],
    config: { responseModalities: ['IMAGE', 'TEXT'] },
  })

  const parts = response.candidates?.[0]?.content?.parts ?? []
  const imagePart = parts.find((p) => p.inlineData?.mimeType?.startsWith('image/'))
  if (!imagePart?.inlineData?.data) return null

  return Buffer.from(imagePart.inlineData.data, 'base64')
}
