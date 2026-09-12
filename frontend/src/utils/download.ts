/**
 * 触发浏览器下载同源/跨域资源。
 * 同源 /static 资源优先用 <a download>；跨域回退 fetch blob。
 */
export async function downloadFile(url: string, filename: string): Promise<void> {
  const name = filename || fallbackName(url)

  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  if (url.startsWith('/') || (origin && url.startsWith(origin))) {
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
    return
  }

  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`下载失败: ${res.status}`)
  }
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objectUrl)
}

function fallbackName(url: string): string {
  const path = url.split('?')[0] ?? url
  const seg = path.split('/').filter(Boolean).pop()
  return seg || 'asset'
}
