/**
 * AmbientBackground — renders animated background effects (particles, matrix rain, aurora, fireflies).
 * Uses a canvas element behind the main content. The animation type is driven by CSS variables.
 */

import { useRef, useEffect, useCallback } from 'react'
import { useAmbientStore } from '@/stores'

/** Simple particle system for the "particles" ambient type */
function drawParticles(
  ctx: CanvasRenderingContext2D,
  w: number, h: number,
  particles: { x: number; y: number; vx: number; vy: number; r: number; a: number }[],
  color: string,
) {
  ctx.clearRect(0, 0, w, h)
  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    if (p.x < 0 || p.x > w) p.vx *= -1
    if (p.y < 0 || p.y > h) p.vy *= -1
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fillStyle = `${color}${Math.round(p.a * 255).toString(16).padStart(2, '0')}`
    ctx.fill()
  }
}

function createParticles(w: number, h: number, count = 40) {
  return Array.from({ length: count }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    r: Math.random() * 2 + 0.5,
    a: Math.random() * 0.3 + 0.05,
  }))
}

export function AmbientBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number>(0)
  const particlesRef = useRef<ReturnType<typeof createParticles>>([])
  const theme = useAmbientStore((s) => s.getCurrentTheme())

  const animate = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const type = theme.ambient.type
    if (type === 'none') {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      return
    }

    if (type === 'particles' || type === 'fireflies') {
      drawParticles(ctx, canvas.width, canvas.height, particlesRef.current, theme.colors.primary)
    } else if (type === 'matrix_rain') {
      // Simplified matrix effect
      ctx.fillStyle = 'rgba(0, 0, 0, 0.05)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.fillStyle = theme.colors.primary + '40'
      ctx.font = '12px monospace'
      for (let i = 0; i < 20; i++) {
        const x = Math.random() * canvas.width
        const y = Math.random() * canvas.height
        ctx.fillText(String.fromCharCode(0x30A0 + Math.random() * 96), x, y)
      }
    } else if (type === 'aurora') {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      const time = Date.now() / 3000
      const grad = ctx.createLinearGradient(0, 0, canvas.width, canvas.height)
      grad.addColorStop(0, theme.colors.gradient[0] + '10')
      grad.addColorStop(0.5 + Math.sin(time) * 0.3, theme.colors.gradient[1] + '08')
      grad.addColorStop(1, theme.colors.primary + '05')
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, canvas.width, canvas.height)
    }

    animationRef.current = requestAnimationFrame(animate)
  }, [theme])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      particlesRef.current = createParticles(canvas.width, canvas.height)
    }

    resize()
    window.addEventListener('resize', resize)
    animationRef.current = requestAnimationFrame(animate)

    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animationRef.current)
    }
  }, [animate])

  if (theme.ambient.type === 'none') return null

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      aria-hidden
    />
  )
}
