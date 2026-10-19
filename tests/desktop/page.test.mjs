// Spec today-page, rendered without a browser: pure views expanded into a plain tree.
import { test } from 'node:test'
import assert from 'node:assert/strict'

const page = await import('../../desktop/plugin.js')
const { TodayView, SectionCard, MergeDialog, refreshSection, previewMerge, confirmMerge } = page

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

test('refresh one section calls its route', async () => {
  const calls = []
  const rest = async (path, opts) => { calls.push([path, opts?.method]); return {} }
  let refreshed = null
  const tree = render(SectionCard({ section: prs(), onRefresh: id => { refreshed = id; return refreshSection(rest, id) } }))
  await byAction(tree, 'refresh')[0].props.onClick()
  assert.equal(refreshed, 'prs')
  assert.deepEqual(calls, [['/sections/prs/refresh', 'POST']])
})

test('merge control only when enabled', () => {
  const off = render(SectionCard({ section: prs() }))
  assert.equal(byAction(off, 'merge').length, 0)
  const on = render(SectionCard({ section: prs({ merge: true }) }))
  assert.equal(byAction(on, 'merge').length, 1) // the draft gets none
})

const previewData = { token: 'tok', repo: 'owner/repo', number: 7, title: 'T', base: 'main', head: 'abc1234def5678', method: 'squash' }

test('preview shown and cancelled', async () => {
  const calls = []
  const rest = async (path, opts) => { calls.push([path, opts?.body]); return previewData }
  const section = prs({ merge: true })
  let shown = null
  const tree = render(SectionCard({ section, onMerge: async (s, item) => { shown = await previewMerge(rest, s.id, item) } }))
  await byAction(tree, 'merge')[0].props.onClick()
  assert.deepEqual(calls, [['/sections/prs/merge/preview', { repo: 'owner/repo', number: 7 }]])
  let cancelled = false
  let confirmed = false
  const dialog = render(MergeDialog({ preview: shown, onCancel: () => { cancelled = true }, onConfirm: () => { confirmed = true } }))
  assert.match(textOf(byRole(dialog, 'merge-target')), /owner\/repo#7/)
  assert.match(textOf(byRole(dialog, 'merge-details')), /into main · squash/)
  byAction(dialog, 'merge-cancel')[0].props.onClick()
  assert.equal(cancelled, true)
  assert.equal(confirmed, false)
  assert.equal(calls.length, 1)
})

test('confirm sends the token and shows merged', async () => {
  const calls = []
  const rest = async (path, opts) => { calls.push([path, opts?.body]); return { merged: true } }
  let result = null
  const dialog = render(MergeDialog({ preview: previewData, onConfirm: async token => { result = await confirmMerge(rest, token) } }))
  await byAction(dialog, 'merge-confirm')[0].props.onClick()
  assert.deepEqual(calls, [['/merge/confirm', { token: 'tok' }]])
  const after = render(MergeDialog({ preview: previewData, result }))
  assert.equal(textOf(byRole(after, 'merge-result')), 'Merged.')
  assert.equal(byAction(after, 'merge-confirm').length, 0)
})

test('merge error shown', () => {
  const dialog = render(MergeDialog({ preview: previewData, error: 'gh exited with status 1: Head branch was modified' }))
  assert.match(textOf(byRole(dialog, 'merge-error')), /Head branch was modified/)
  assert.equal(byAction(dialog, 'merge-confirm').length, 0)
})

test('register adds the page, the nav entry and the palette command', () => {
  const added = []
  page.default.register({ rest: async () => ({}), registerMany: items => { added.push(...items); return () => {} } })
  assert.deepEqual(added.map(a => a.area), ['routes', 'sidebar-nav', 'palette'])
  assert.equal(added[0].data.path, '/today')
})
