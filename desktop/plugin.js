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
  Codicon,
  EmptyState,
  ErrorState,
  GlyphSpinner,
  host,
  PALETTE_AREA,
  ROUTES_AREA,
  ScrollArea,
  SIDEBAR_NAV_AREA,
  StatusDot,
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

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** Short time for a row or a header: "just now", "5 min ago", "in 2 h", "14:05" (today),
 *  "16 Oct 17:28" (other days). The full time goes in the element's title. */
export function shortTime (value, now = Date.now()) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return text(value)
  const pad = n => String(n).padStart(2, '0')
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  const minutes = Math.round((d.getTime() - now) / 60000)
  if (Math.abs(minutes) < 1) return 'just now'
  if (minutes < 0 && minutes > -60) return `${-minutes} min ago`
  if (minutes > 0 && minutes < 60) return `in ${minutes} min`
  if (minutes > 0 && minutes < 24 * 60) return `in ${Math.round(minutes / 60)} h`
  if (new Date(now).toDateString() === d.toDateString()) return hm
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${hm}`
}

const STATUS_TONE = { ok: 'good', stale: 'warn', error: 'bad' }

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
export function ItemRow ({ section, item, onOpen, onMerge, now }) {
  const link = safeLink(item.url)
  const merge = canMerge(section, item)
  const title = link
    ? jsx('a', {
      href: link, 'data-action': 'open', className: `${ID}-link`, title: link,
      onClick: e => { e?.preventDefault?.(); onOpen?.(link) }, children: text(item.title)
    })
    : jsx('span', { 'data-role': 'title', className: `${ID}-title`, children: text(item.title) })
  // A row is a small grid: title and badge on the left, time on the right; details and the
  // merge action under the title. A long title wraps inside its own column.
  return jsxs('li', {
    className: `${ID}-item`,
    children: [
      jsxs('div', {
        className: `${ID}-item-main`,
        children: [title, item.badge ? jsx(Badge, { variant: 'muted', 'data-role': 'badge', children: text(item.badge) }) : null]
      }),
      item.time
        ? jsx('span', { className: `${ID}-time`, 'data-role': 'time', title: formatTime(item.time), children: shortTime(item.time, now) })
        : null,
      item.detail || merge
        ? jsxs('div', {
          className: `${ID}-item-sub`,
          children: [
            item.detail ? jsx('span', { 'data-role': 'detail', children: text(item.detail) }) : null,
            merge
              ? jsxs(Button, {
                size: 'xs', variant: 'outline', 'data-action': 'merge', onClick: () => onMerge?.(section, item),
                children: [jsx(Codicon, { name: 'git-merge', 'aria-hidden': true }), 'Merge…']
              })
              : null
          ]
        })
        : null
    ]
  })
}

export function SectionCard ({ section, busy = false, onRefresh, onOpen, onMerge, now }) {
  const items = section.items || []
  const more = section.total > items.length ? `${items.length} of ${section.total}` : ''
  const status = text(section.status)
  return jsxs('section', {
    className: `${ID}-section`,
    'data-section': section.id,
    'data-status': status,
    children: [
      jsxs('header', {
        className: `${ID}-head`,
        children: [
          jsx(StatusDot, { tone: STATUS_TONE[status] || 'muted', 'data-role': 'status-dot', title: status }),
          jsx('h3', { 'data-role': 'section-title', children: text(section.title) }),
          more ? jsx('span', { className: `${ID}-count`, 'data-role': 'count', children: more }) : null,
          status !== 'ok'
            ? jsx(Badge, { variant: status === 'error' ? 'destructive' : 'warn', 'data-role': 'status', children: status })
            : null,
          jsx('span', { className: `${ID}-spacer` }),
          section.read_at
            ? jsx('span', { className: `${ID}-time`, 'data-role': 'read-at', title: `read ${formatTime(section.read_at)}`, children: shortTime(section.read_at, now) })
            : null,
          jsx(Button, {
            size: 'xs', variant: 'ghost', 'data-action': 'refresh', disabled: busy,
            title: `Refresh ${text(section.title)}`, 'aria-label': `Refresh ${text(section.title)}`,
            onClick: () => onRefresh?.(section.id),
            children: jsx(Codicon, { name: 'refresh', spinning: busy, 'aria-hidden': true })
          })
        ]
      }),
      section.error ? jsx('div', { className: `${ID}-error`, 'data-role': 'error', children: text(section.error) }) : null,
      items.length
        ? jsx('ul', { className: `${ID}-items`, children: items.map((item, i) => jsx(ItemRow, { section, item, onOpen, onMerge, now }, `${i}-${text(item.title)}`)) })
        : (section.status === 'error' ? null : jsx('div', { className: `${ID}-empty`, 'data-role': 'empty', children: 'Nothing here.' })),
      section.note ? jsx('div', { className: `${ID}-note`, 'data-role': 'note', children: text(section.note) }) : null
    ]
  })
}

export function TodayView ({ data, busy = {}, notice = '', onRefresh, onRefreshAll, onOpen, onMerge, now = Date.now() }) {
  const errors = data?.errors || []
  const toolbar = jsxs('div', {
    className: `${ID}-toolbar`,
    children: [
      jsx('h2', { children: 'Today' }),
      jsx('span', { className: `${ID}-date`, 'data-role': 'date', children: text(data?.date) }),
      jsx('span', { className: `${ID}-spacer` }),
      notice ? jsx('span', { className: `${ID}-notice`, 'data-role': 'notice', children: text(notice) }) : null,
      jsxs(Button, {
        size: 'sm', variant: 'outline', 'data-action': 'refresh-all', disabled: !!busy['*'], onClick: () => onRefreshAll?.(),
        children: [jsx(Codicon, { name: 'refresh', spinning: !!busy['*'], 'aria-hidden': true }), busy['*'] ? 'Reading…' : 'Refresh all']
      })
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
        ? jsx('div', {
          className: `${ID}-grid`,
          children: sections.map(s => jsx(SectionCard, { section: s, busy: !!busy[s.id], onRefresh, onOpen, onMerge, now }, s.id))
        })
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
      jsx('div', { className: `${ID}-note`, 'data-role': 'merge-details', children: `into ${text(preview.base)} · ${text(preview.method)} · head ${text(preview.head).slice(0, 12)}` }),
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

// The page follows the Desktop theme: every colour comes from the Desktop's `--color-*` tokens
// (with the plain shadcn names, then a neutral value, as fallbacks). A theme's custom CSS can
// restyle the page by overriding the `--dp-*` variables below on `.day-panel-page`.
const STYLE = `
.${ID}-page{
  --dp-fg:var(--color-foreground,var(--foreground,inherit));
  --dp-muted:var(--color-muted-foreground,var(--muted-foreground,#8a8a8a));
  --dp-border:var(--color-border,var(--border,rgba(128,128,128,.25)));
  --dp-card:var(--color-card,var(--card,transparent));
  --dp-link:var(--color-primary,var(--primary,#2f6fdd));
  --dp-danger:var(--color-destructive,var(--destructive,#d0393e));
  --dp-hover:color-mix(in srgb,var(--dp-fg) 5%,transparent);
  --dp-radius:var(--radius-lg,10px);
  --dp-columns:minmax(360px,1fr);
  display:flex;flex-direction:column;gap:16px;padding:20px 24px 32px;max-width:1280px;color:var(--dp-fg)
}
.${ID}-toolbar{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.${ID}-toolbar h2{margin:0;font-size:20px;font-weight:600;letter-spacing:-.01em}
.${ID}-date{color:var(--dp-muted);font-size:13px}
.${ID}-spacer{flex:1}
.${ID}-notice{color:var(--dp-danger);font-size:12px}
.${ID}-grid{display:grid;grid-template-columns:repeat(auto-fill,var(--dp-columns));gap:14px;align-items:start}
.${ID}-section{background:var(--dp-card);border:1px solid var(--dp-border);border-radius:var(--dp-radius);padding:10px 8px 8px;display:flex;flex-direction:column;gap:4px;min-width:0}
.${ID}-section[data-status="error"]{border-color:color-mix(in srgb,var(--dp-danger) 45%,var(--dp-border))}
.${ID}-head{display:flex;align-items:center;gap:8px;padding:0 6px 4px;min-height:26px}
.${ID}-head h3{margin:0;font-size:13px;font-weight:600}
.${ID}-count,.${ID}-time{color:var(--dp-muted);font-size:11.5px;white-space:nowrap;font-variant-numeric:tabular-nums}
.${ID}-items{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
.${ID}-item{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:12px;row-gap:1px;padding:6px;border-radius:calc(var(--dp-radius) - 4px)}
.${ID}-item:hover{background:var(--dp-hover)}
.${ID}-item-main{display:flex;align-items:center;gap:6px;min-width:0;flex-wrap:wrap;font-size:13px;line-height:1.35}
.${ID}-item > .${ID}-time{align-self:start;padding-top:2px}
.${ID}-item-sub{grid-column:1 / -1;display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:var(--dp-muted);font-size:12px}
.${ID}-link{color:var(--dp-link);text-decoration:none;overflow-wrap:anywhere;cursor:pointer}
.${ID}-link:hover{text-decoration:underline}
.${ID}-title{overflow-wrap:anywhere}
.${ID}-empty{color:var(--dp-muted);font-size:12px;font-style:italic;padding:4px 6px}
.${ID}-note{color:var(--dp-muted);font-size:12px;padding:2px 6px}
.${ID}-error{color:var(--dp-danger);font-size:12px;padding:6px 8px;border-radius:calc(var(--dp-radius) - 4px);background:color-mix(in srgb,var(--dp-danger) 8%,transparent);overflow-wrap:anywhere}
.${ID}-actions{display:flex;gap:8px;margin-top:6px}
.${ID}-dialog{position:fixed;right:24px;bottom:24px;width:min(480px,calc(100vw - 48px));background:var(--color-popover,var(--dp-card));color:var(--dp-fg);border:1px solid var(--dp-border);border-radius:var(--dp-radius);padding:16px;display:flex;flex-direction:column;gap:6px;z-index:50;box-shadow:0 12px 32px rgba(0,0,0,.18)}
.${ID}-dialog h3{margin:0 0 2px;font-size:14px;font-weight:600}
`

function ensureStyles () {
  if (typeof document === 'undefined') return
  let el = document.getElementById(`${ID}-style`)
  if (!el) {
    el = document.createElement('style')
    el.id = `${ID}-style`
    document.head.appendChild(el)
  }
  el.textContent = STYLE // always the current rules: Desktop hot-reloads plugin.js without a page reload
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
