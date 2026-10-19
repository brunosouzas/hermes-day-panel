// Spec today-page, rendered without a browser: pure views expanded into a plain tree.
import { test } from 'node:test'
import assert from 'node:assert/strict'

const page = await import('../../desktop/plugin.js')
const { TodayView, SectionCard, MergeDialog, TodayPage, createController, refreshSection, previewMerge, confirmMerge, shortTime } = page
const sdk = await import('@hermes/plugin-sdk')

function render (node) {
  if (node == null || node === false) return null
  if (Array.isArray(node)) return node.map(render)
  if (typeof node !== 'object') return node
  if (typeof node.type === 'function') return render(node.type(node.props))
  const children = node.props?.children
  return { type: node.type, props: { ...node.props, children: children === undefined ? undefined : render(children) } }
}

function all (tree, pred, out = []) {
  if (Array.isArray(tree)) { tree.forEach(t => all(t, pred, out)); return out }
  if (!tree || typeof tree !== 'object') return out
  if (pred(tree)) out.push(tree)
  all(tree.props?.children, pred, out)
  return out
}
const byRole = (tree, role) => all(tree, n => n.props?.['data-role'] === role)
const byAction = (tree, action) => all(tree, n => n.props?.['data-action'] === action)
const textOf = node => {
  if (node == null) return ''
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (typeof node !== 'object') return String(node)
  return textOf(node.props?.children)
}
const htmlProps = tree => all(tree, n => n.props && 'dangerouslySetInnerHTML' in n.props)

const pr = (number, draft = false) => ({
  title: `owner/repo#${number} · T`, url: `https://github.com/owner/repo/pull/${number}`, pr: { repo: 'owner/repo', number, draft }
})
const prs = (over = {}) => ({
  id: 'prs', title: 'Pull requests', kind: 'github_prs', status: 'ok', items: [pr(7), pr(8, true)], total: 2,
  note: null, error: null, read_at: '2026-10-19T12:00:00+00:00', merge: false, ...over
})
const usage = { id: 'usage', title: 'AI usage', kind: 'ai_usage', status: 'error', items: [], total: 0, error: 'no credential', merge: false }
const data = (sections, errors = []) => ({ date: '2026-10-19', sources_file: '/x/sources.yaml', errors, sections })

test('Sections shown', () => {
  const tree = render(TodayView({ data: data([prs(), usage]) }))
  const sections = all(tree, n => n.type === 'section')
  assert.deepEqual(sections.map(s => s.props['data-section']), ['prs', 'usage'])
  assert.equal(all(sections[0], n => n.type === 'li').length, 2)
  assert.equal(textOf(byRole(sections[1], 'error')), 'no credential')
  assert.equal(textOf(byRole(sections[1], 'status')), 'error')
})

test('short times read naturally, past and future', () => {
  const now = new Date(2026, 9, 19, 15, 0).getTime()
  const at = (d, h, m) => new Date(2026, 9, d, h, m).toISOString()
  assert.equal(shortTime(at(19, 15, 0), now), 'just now')
  assert.equal(shortTime(at(19, 14, 48), now), '12 min ago')
  assert.equal(shortTime(at(19, 15, 40), now), 'in 40 min')
  assert.equal(shortTime(at(19, 18, 10), now), 'in 3 h')
  assert.equal(shortTime(at(19, 9, 5), now), '09:05')
  assert.equal(shortTime(at(16, 17, 28), now), '16 Oct 17:28')
  assert.equal(shortTime('not a date', now), 'not a date')
})

test('status shown as a dot, with a word only when it is not ok', () => {
  const ok = render(SectionCard({ section: prs() }))
  assert.equal(byRole(ok, 'status').length, 0)
  assert.equal(byRole(ok, 'status-dot')[0].props.tone, 'good')
  const stale = render(SectionCard({ section: prs({ status: 'stale' }) }))
  assert.equal(textOf(byRole(stale, 'status')), 'stale')
  assert.equal(byRole(stale, 'status-dot')[0].props.tone, 'warn')
})

const usageSection = items => prs({ id: 'ai', title: 'AI usage', items, total: items.length })

test('Usage window', () => {
  const now = Date.parse('2026-10-19T15:20:00Z')
  const item = { title: 'Claude · Current session', progress: 68, tone: 'warn', time_label: 'resets', time: '2026-10-19T16:00:00Z' }
  const tree = render(SectionCard({ section: usageSection([item]), now }))
  const [bar] = byRole(tree, 'progress')
  assert.equal(bar.props['data-tone'], 'warn')
  assert.equal(bar.props['aria-valuenow'], 68)
  assert.equal(bar.props.children.props.style.width, '68%')
  assert.equal(textOf(byRole(tree, 'time')), 'resets in 40 min')
})

test('Badge coloured by tone', () => {
  const tree = render(SectionCard({ section: usageSection([{ title: 'build 1', badge: 'failed', tone: 'bad' }, { title: 'build 2', badge: 'ok' }]) }))
  const badges = byRole(tree, 'badge')
  assert.deepEqual(badges.map(b => [textOf([b]), b.props.variant]), [['failed', 'destructive'], ['ok', 'muted']])
  assert.equal(byRole(tree, 'tone-dot').length, 0) // a badge carries the tone; no dot as well
})

test('Tone without a badge', () => {
  const tree = render(SectionCard({ section: usageSection([{ title: 'deploy', tone: 'good' }]) }))
  const [dot] = byRole(tree, 'tone-dot')
  assert.equal(dot.props['data-tone'], 'good')
  const main = all(tree, n => n.props?.className === 'day-panel-item-main')[0]
  assert.equal(main.props.children.filter(Boolean)[0], dot) // before the title
})

test('Empty bar and no tone', () => {
  const tree = render(SectionCard({ section: usageSection([{ title: 'quota', progress: 0 }]) }))
  const [bar] = byRole(tree, 'progress')
  assert.equal(bar.props['data-tone'], 'none') // the primary colour
  assert.equal(bar.props.children.props.style.width, '0%')
  assert.equal(byRole(tree, 'tone-dot').length, 0)
  assert.equal(byRole(tree, 'time').length, 0)
  // a value the backend would have dropped never draws a bar here either
  const odd = render(SectionCard({ section: usageSection([{ title: 'q', progress: '50' }, { title: 'r', progress: 140 }]) }))
  assert.equal(byRole(odd, 'progress').length, 0)
})

test('Markup in source text', () => {
  const evil = '<img src=x onerror=alert(1)>'
  const tree = render(SectionCard({ section: prs({ items: [{ title: evil, detail: evil }] }) }))
  assert.equal(textOf(byRole(tree, 'title')), evil)
  assert.equal(htmlProps(tree).length, 0)
  assert.equal(all(tree, n => n.type === 'img').length, 0)
})

test('Invalid sources file', () => {
  const tree = render(TodayView({ data: data([], ['section cal: unknown kind']) }))
  assert.match(textOf(byRole(tree, 'config-errors')), /unknown kind/)
  assert.equal(all(tree, n => n.type === 'section').length, 0)
})

test('Item without a link', () => {
  const tree = render(SectionCard({ section: prs({ items: [{ title: 'plain' }, { title: 'bad', url: 'javascript:alert(1)' }] }) }))
  assert.equal(byAction(tree, 'open').length, 0)
  assert.deepEqual(byRole(tree, 'title').map(textOf), ['plain', 'bad'])
})

// A fake backend: answers by path and records every call.
function backend (answers = {}) {
  const calls = []
  const restFn = async (path, opts = {}) => {
    calls.push([path, opts.method || 'GET', opts.body])
    const answer = answers[path]
    if (answer instanceof Error) throw answer
    return typeof answer === 'function' ? answer() : (answer ?? {})
  }
  return { calls, restFn }
}

test('refresh one section calls its route', async () => {
  const { calls, restFn } = backend()
  let reloads = 0
  const states = []
  const c = createController({ restFn, reload: () => { reloads++ }, onChange: s => states.push({ ...s.busy }) })
  const tree = render(SectionCard({ section: prs(), onRefresh: c.refresh }))
  await byAction(tree, 'refresh')[0].props.onClick()
  assert.deepEqual(calls.map(x => x.slice(0, 2)), [['/sections/prs/refresh', 'POST']])
  assert.equal(reloads, 1) // the page's query is invalidated, so it shows the new read time
  assert.deepEqual(states[0], { prs: true })
  assert.deepEqual(c.state.busy, { prs: false })
  const readAt = '2026-10-19T13:05:00+00:00'
  const after = render(SectionCard({ section: prs({ read_at: readAt }), now: Date.parse(readAt) + 3 * 60000 }))
  const [shown] = byRole(after, 'read-at')
  assert.equal(textOf([shown]), '3 min ago')
  assert.match(shown.props.title, /^read 2026-10-19 \d\d:05$/) // the full time stays on hover
})

test('page polls every 60 seconds and renders the sections it gets', () => {
  sdk.recorded.queries.length = 0
  sdk.queryResult.value = { data: data([prs()]), isLoading: false, isError: false }
  const tree = render(TodayPage())
  const [query] = sdk.recorded.queries
  assert.equal(query.refetchInterval, 60000)
  assert.deepEqual(query.queryKey, ['day-panel', 'sections'])
  assert.equal(all(tree, n => n.type === 'section').length, 1)
  sdk.queryResult.value = { data: undefined, isLoading: false, isError: false }
})

test('a failed refresh shows its error', async () => {
  const { restFn } = backend({ '/sections/prs/refresh': new Error('{"detail":{"code":"not_found","message":"no such section"}}') })
  const c = createController({ restFn, reload: () => {} })
  await c.refresh('prs')
  assert.equal(c.state.notice, 'no such section')
  assert.equal(c.state.busy.prs, false)
})

test('merge control only when enabled', () => {
  const off = render(SectionCard({ section: prs() }))
  assert.equal(byAction(off, 'merge').length, 0)
  const on = render(SectionCard({ section: prs({ merge: true }) }))
  assert.equal(byAction(on, 'merge').length, 1) // the draft gets none
})

const previewData = { token: 'tok', repo: 'owner/repo', number: 7, title: 'T', base: 'main', head: 'abc1234def5678', method: 'squash' }

const dialogOf = c => render(MergeDialog({ preview: c.state.preview, busy: c.state.mergeBusy, result: c.state.mergeResult,
  error: c.state.mergeError, onConfirm: c.confirm, onCancel: c.cancel }))

test('preview shown and cancelled', async () => {
  const { calls, restFn } = backend({ '/sections/prs/merge/preview': previewData })
  const c = createController({ restFn, reload: () => {} })
  const tree = render(SectionCard({ section: prs({ merge: true }), onMerge: c.merge }))
  await byAction(tree, 'merge')[0].props.onClick()
  assert.deepEqual(calls, [['/sections/prs/merge/preview', 'POST', { repo: 'owner/repo', number: 7 }]])
  const dialog = dialogOf(c)
  assert.match(textOf(byRole(dialog, 'merge-target')), /owner\/repo#7/)
  assert.match(textOf(byRole(dialog, 'merge-details')), /into main · squash/)
  byAction(dialog, 'merge-cancel')[0].props.onClick()
  assert.equal(dialogOf(c), null) // the dialog is gone
  assert.equal(calls.length, 1) // and no confirm was sent
})

test('confirm sends the token and shows merged', async () => {
  const { calls, restFn } = backend({ '/sections/prs/merge/preview': previewData, '/merge/confirm': { merged: true } })
  let reloads = 0
  const c = createController({ restFn, reload: () => { reloads++ } })
  await c.merge(prs({ merge: true }), pr(7))
  await byAction(dialogOf(c), 'merge-confirm')[0].props.onClick()
  assert.deepEqual(calls[1], ['/merge/confirm', 'POST', { token: 'tok' }])
  const after = dialogOf(c)
  assert.equal(textOf(byRole(after, 'merge-result')), 'Merged.')
  assert.equal(byAction(after, 'merge-confirm').length, 0)
  assert.equal(reloads, 1)
})

test('merge error shown', async () => {
  const { restFn } = backend({
    '/sections/prs/merge/preview': previewData,
    '/merge/confirm': new Error('{"detail":{"code":"merge_failed","message":"gh exited with status 1: Head branch was modified"}}')
  })
  const c = createController({ restFn, reload: () => {} })
  await c.merge(prs({ merge: true }), pr(7))
  await c.confirm('tok')
  const dialog = dialogOf(c)
  assert.match(textOf(byRole(dialog, 'merge-error')), /Head branch was modified/)
  assert.equal(byAction(dialog, 'merge-confirm').length, 0)
  assert.equal(c.state.mergeBusy, false)
})

test('register adds the page, the nav entry and the palette command', () => {
  const added = []
  page.default.register({ rest: async () => ({}), registerMany: items => { added.push(...items); return () => {} } })
  assert.deepEqual(added.map(a => a.area), ['routes', 'sidebar-nav', 'palette'])
  assert.equal(added[0].data.path, '/today')
})
