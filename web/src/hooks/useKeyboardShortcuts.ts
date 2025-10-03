import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export function useKeyboardShortcuts() {
  const navigate = useNavigate()

  useEffect(() => {
    let isComboMode = false
    let comboTimeout: NodeJS.Timeout

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return
      }

      if (e.key === '/') {
        e.preventDefault()
        const searchInput = document.querySelector('input[type="search"]') as HTMLInputElement
        searchInput?.focus()
        return
      }

      if (e.key === 'g' && !isComboMode) {
        isComboMode = true
        clearTimeout(comboTimeout)
        comboTimeout = setTimeout(() => {
          isComboMode = false
        }, 1000)
        return
      }

      if (isComboMode) {
        switch (e.key) {
          case 'v': navigate('/venues'); break
          case 'o': navigate('/orders'); break
          case 'r': navigate('/risk'); break
          case 'a': navigate('/alerts'); break
          case 'l': navigate('/live'); break
        }
        isComboMode = false
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      clearTimeout(comboTimeout)
    }
  }, [navigate])
}
