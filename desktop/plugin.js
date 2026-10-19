/**
 * Today: the Desktop page for hermes-day-panel.
 *
 * Shows the sections of the user's sources file through this plugin's backend
 * (dashboard/plugin_api.py, mounted by Hermes at /api/plugins/day-panel/ only
 * while the plugin is enabled). Refreshes every 60 s while open, and on demand
 * per section. A github_prs section with merge enabled offers "Merge…": a preview
 * first, then an explicit confirmation.
 *
 * Every source text is rendered as a React text child, never as HTML. Links open
 * only when they are http(s), through the host's external opener.
 *
 * Plain ESM loaded uncompiled: UI is jsx() calls, not JSX syntax; only
 * @hermes/plugin-sdk, react and react/jsx-runtime resolve. The views are pure
 * functions of their props so tests/desktop/ can render them in Node.
 */

import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  GlyphSpinner,
  host,
  PALETTE_AREA,
  ROUTES_AREA,
  ScrollArea,
  SIDEBAR_NAV_AREA,
  queryClient,
  useQuery
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useRef, useState } from 'react'

export const ID = 'day-panel'
const PAGE_PATH = '/today'
const POLL_MS = 60000
const QUERY_KEY = [ID, 'sections']

let rest = null
let openExternalFn = async () => false

export function setRuntime ({ restFn, openExternal }) {
  rest = restFn
  if (openExternal) openExternalFn = openExternal
}

// ── helpers ────────────────────────────────────────────────────────────────
export function errText (e) {
  const raw = String(e?.message || e || '')
  const m = /"message"\s*:\s*"((?:[^"\\]|\\.)*)"/.exec(raw)
  if (m) {
    try { return JSON.parse(`"${m[1]}"`) } catch { /* fall through */ }
  }
  return raw.slice(0, 300)
}

export function safeLink (link) {
  return typeof link === 'string' && /^https?:\/\//i.test(link) ? link : null
}

function text (value) {
  return typeof value === 'string' ? value : value == null ? '' : String(value)
}

export function formatTime (value) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return text(value)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function canMerge (section, item) {
  return !!(section?.merge && item?.pr && !item.pr.draft)
}

// ── requests (exported so tests can drive them with a fake rest) ───────────
export const refreshSection = (restFn, id) => restFn(`/sections/${encodeURIComponent(id)}/refresh`, { method: 'POST' })
export const refreshAll = restFn => restFn('/refresh', { method: 'POST' })
export const previewMerge = (restFn, sectionId, item) =>
  restFn(`/sections/${encodeURIComponent(sectionId)}/merge/preview`, {
    method: 'POST', body: { repo: item.pr.repo, number: item.pr.number }
  })
export const confirmMerge = (restFn, token) => restFn('/merge/confirm', { method: 'POST', body: { token } })

// ── pure views ─────────────────────────────────────────────────────────────
const STATUS_LABEL = { ok: 'ok', stale: 'stale', error: 'error' }

export function ItemRow ({ section, item, onOpen, onMerge }) {
  const link = safeLink(item.url)
  const meta = [
    item.detail ? jsx('span', { 'data-role': 'detail', children: text(item.detail) }, 'd') : null,
    item.time ? jsx('span', { 'data-role': 'time', children: formatTime(item.time) }, 't') : null
  ].filter(Boolean)
  const merge = canMerge(section, item)
  // Two lines per item: the title (with its badge), then the details and actions, so a long
  // title never pushes one item's details next to the following item.
  return jsxs('li', {
    className: `${ID}-item`,
    children: [
      jsxs('div', {
        className: `${ID}-item-line`,
        children: [
          link
            ? jsx('a', {
              href: link, 'data-action': 'open', className: `${ID}-link`,
              onClick: e => { e?.preventDefault?.(); onOpen?.(link) }, children: text(item.title)
            })
            : jsx('span', { 'data-role': 'title', children: text(item.title) }),
          item.badge ? jsx(Badge, { 'data-role': 'badge', children: text(item.badge) }) : null
        ]
      }),
      meta.length || merge
        ? jsxs('div', {
          className: `${ID}-item-line ${ID}-muted`,
          children: [
            ...meta,
            merge ? jsx(Button, { size: 'sm', variant: 'ghost', 'data-action': 'merge', onClick: () => onMerge?.(section, item), children: 'Merge…' }) : null
          ]
        })
        : null
    ]
  })
}

export function SectionCard ({ section, busy = false, onRefresh, onOpen, onMerge }) {
  const items = section.items || []
  const more = section.total > items.length ? ` (${items.length} of ${section.total})` : ''
  return jsxs('section', {
    className: `${ID}-section`,
    'data-section': section.id,
    children: [
      jsxs('header', {
        className: `${ID}-head`,
        children: [
          jsx('h3', { 'data-role': 'section-title', children: text(section.title) + more }),
          jsx(Badge, { 'data-role': 'status', children: STATUS_LABEL[section.status] || text(section.status) }),
          section.read_at ? jsx('span', { className: `${ID}-muted`, 'data-role': 'read-at', children: `read ${formatTime(section.read_at)}` }) : null,
          jsx(Button, {
            size: 'sm', variant: 'ghost', 'data-action': 'refresh', disabled: busy,
            onClick: () => onRefresh?.(section.id), children: busy ? 'Reading…' : 'Refresh'
          })
        ]
      }),
      section.error ? jsx('div', { className: `${ID}-error`, 'data-role': 'error', children: text(section.error) }) : null,
      items.length
        ? jsx('ul', { className: `${ID}-items`, children: items.map((item, i) => jsx(ItemRow, { section, item, onOpen, onMerge }, `${i}-${text(item.title)}`)) })
        : (section.status === 'error' ? null : jsx('div', { className: `${ID}-muted`, 'data-role': 'empty', children: 'Nothing here.' })),
      section.note ? jsx('div', { className: `${ID}-muted`, 'data-role': 'note', children: text(section.note) }) : null
    ]
  })
}

export function TodayView ({ data, busy = {}, notice = '', onRefresh, onRefreshAll, onOpen, onMerge }) {
  const errors = data?.errors || []
  const toolbar = jsxs('div', {
    className: `${ID}-toolbar`,
    children: [
      jsx('h2', { children: `Today — ${text(data?.date)}` }),
      jsx(Button, { size: 'sm', 'data-action': 'refresh-all', disabled: !!busy['*'], onClick: () => onRefreshAll?.(), children: busy['*'] ? 'Reading…' : 'Refresh all' }),
      notice ? jsx('span', { className: `${ID}-muted`, 'data-role': 'notice', children: text(notice) }) : null
    ]
  })
  if (errors.length) {
    return jsxs('div', {
      className: `${ID}-page`,
      children: [
        toolbar,
        jsxs('div', {
          className: `${ID}-error`, 'data-role': 'config-errors',
          children: [
            jsx('div', { children: `The sources file cannot be used: ${text(data?.sources_file)}` }),
            jsx('ul', { children: errors.map((e, i) => jsx('li', { children: text(e) }, i)) })
          ]
        })
      ]
    })
  }
  const sections = data?.sections || []
  return jsxs('div', {
    className: `${ID}-page`,
    children: [
      toolbar,
      sections.length
        ? sections.map(s => jsx(SectionCard, { section: s, busy: !!busy[s.id], onRefresh, onOpen, onMerge }, s.id))
        : jsx(EmptyState, { 'data-role': 'no-sections', title: 'No sections', description: 'Every section in the sources file is turned off.' })
    ]
  })
}

export function MergeDialog ({ preview, busy = false, result = null, error = '', onConfirm, onCancel }) {
  if (!preview) return null
  return jsxs('div', {
    className: `${ID}-dialog`, role: 'dialog', 'data-role': 'merge-dialog',
    children: [
      jsx('h3', { children: 'Merge pull request' }),
      jsx('div', { 'data-role': 'merge-target', children: `${text(preview.repo)}#${text(preview.number)} · ${text(preview.title)}` }),
      jsx('div', { className: `${ID}-muted`, 'data-role': 'merge-details', children: `into ${text(preview.base)} · ${text(preview.method)} · head ${text(preview.head).slice(0, 12)}` }),
      result ? jsx('div', { 'data-role': 'merge-result', children: 'Merged.' }) : null,
      error ? jsx('div', { className: `${ID}-error`, 'data-role': 'merge-error', children: text(error) }) : null,
      jsxs('div', {
        className: `${ID}-actions`,
        children: [
          result || error
            ? jsx(Button, { 'data-action': 'merge-close', onClick: () => onCancel?.(), children: 'Close' })
            : jsx(Button, { 'data-action': 'merge-confirm', disabled: busy, onClick: () => onConfirm?.(preview.token), children: busy ? 'Merging…' : 'Confirm merge' }),
          result || error ? null : jsx(Button, { variant: 'ghost', 'data-action': 'merge-cancel', disabled: busy, onClick: () => onCancel?.(), children: 'Cancel' })
        ]
      })
    ]
  })
}

// ── controller: the page's state and actions, without React (tests drive it directly) ──
export function createController ({ restFn, reload, onChange }) {
  const state = { busy: {}, notice: '', preview: null, mergeBusy: false, mergeResult: null, mergeError: '' }
  const set = patch => { Object.assign(state, patch); onChange?.(state) }
  const withBusy = async (key, call) => {
    set({ busy: { ...state.busy, [key]: true }, notice: '' })
    try { await call(); await reload?.() } catch (e) { set({ notice: errText(e) }) } finally {
      set({ busy: { ...state.busy, [key]: false } })
    }
  }
  return {
    state,
    refresh: id => withBusy(id, () => refreshSection(restFn, id)),
    refreshAll: () => withBusy('*', () => refreshAll(restFn)),
    async merge (section, item) {
      set({ mergeResult: null, mergeError: '', notice: '' })
      try { set({ preview: await previewMerge(restFn, section.id, item) }) } catch (e) { set({ notice: errText(e) }) }
    },
    async confirm (token) {
      set({ mergeBusy: true, mergeError: '' })
      try { set({ mergeResult: await confirmMerge(restFn, token) }); await reload?.() } catch (e) { set({ mergeError: errText(e) }) } finally {
        set({ mergeBusy: false })
      }
    },
    cancel: () => set({ preview: null, mergeResult: null, mergeError: '' })
  }
}

// ── container ──────────────────────────────────────────────────────────────
export function TodayPage () {
  const [, setTick] = useState(0)
  const controller = useRef(null)
  if (!controller.current) {
    controller.current = createController({
      restFn: (...args) => rest(...args),
      reload: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
      onChange: () => setTick(n => n + 1)
    })
  }
  const c = controller.current
  const s = c.state
  const query = useQuery({ queryKey: QUERY_KEY, queryFn: () => rest('/sections'), refetchInterval: POLL_MS })

  if (query.isError) return jsx(ErrorState, { title: 'Today is unavailable', description: errText(query.error) })
  if (query.isLoading) return jsx(GlyphSpinner, {})
  return jsx(ScrollArea, {
    children: jsxs('div', {
      children: [
        jsx(TodayView, {
          data: query.data, busy: s.busy, notice: s.notice,
          onOpen: url => { void openExternalFn(url) }, onRefresh: c.refresh, onRefreshAll: c.refreshAll, onMerge: c.merge
        }),
        jsx(MergeDialog, {
          preview: s.preview, busy: s.mergeBusy, result: s.mergeResult, error: s.mergeError,
          onConfirm: c.confirm, onCancel: c.cancel
        })
      ]
    })
  })
}

const STYLE = `
.${ID}-page{display:flex;flex-direction:column;gap:14px;padding:16px;max-width:900px}
.${ID}-toolbar,.${ID}-actions,.${ID}-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.${ID}-section{border-top:1px solid var(--border);padding-top:10px;display:flex;flex-direction:column;gap:6px}
.${ID}-head h3{margin:0;font-size:14px;font-weight:600}
.${ID}-items{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.${ID}-item{display:flex;flex-direction:column;gap:2px;min-width:0}
.${ID}-item-line{display:flex;flex-wrap:wrap;gap:8px;align-items:center;min-width:0}
.${ID}-link{color:var(--accent);text-decoration:none;overflow-wrap:anywhere;cursor:pointer}
.${ID}-link:hover{text-decoration:underline}
.${ID}-muted{color:var(--muted-foreground);font-size:12px}
.${ID}-error{color:var(--destructive,#c33);font-size:12px}
.${ID}-dialog{position:fixed;right:24px;bottom:24px;max-width:480px;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;display:flex;flex-direction:column;gap:6px;z-index:50}
`

function ensureStyles () {
  if (typeof document === 'undefined' || document.getElementById(`${ID}-style`)) return
  const el = document.createElement('style')
  el.id = `${ID}-style`
  el.textContent = STYLE
  document.head.appendChild(el)
}

export default {
  id: ID,
  name: 'Today',
  description: 'Your day from pluggable, read-only sources: cards, pull requests, pipelines, routine and AI usage.',
  register (ctx) {
    ensureStyles()
    setRuntime({ restFn: ctx.rest, openExternal: ctx.os?.openExternal ? url => ctx.os.openExternal(url) : null })
    return ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: PAGE_PATH }, render: () => jsx(TodayPage, {}) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, order: 60, data: { codicon: 'calendar', label: 'Today', path: PAGE_PATH } },
      {
        id: 'open', area: PALETTE_AREA,
        data: { id: `${ID}.open`, label: 'Today: Open', keywords: ['today', 'day', 'panel', 'dashboard'], run: () => host.navigate(PAGE_PATH) }
      }
    ])
  }
}
