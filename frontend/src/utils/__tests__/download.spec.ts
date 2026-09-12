import { describe, it, expect, vi } from 'vitest'

describe('downloadFile', () => {
  it('跨域 URL 失败时抛错', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    const { downloadFile } = await import('@/utils/download')

    await expect(downloadFile('https://cdn.example.com/v.mp4', 'v.mp4')).rejects.toThrow('下载失败')
    vi.unstubAllGlobals()
  })
})
