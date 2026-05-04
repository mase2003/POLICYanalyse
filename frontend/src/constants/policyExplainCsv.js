/**
 * 与 backend/services/policy_explain_service.py 中 CSV_COLUMNS、text1.py 导入列一致。
 */
export const POLICY_EXPLAIN_CSV_COLUMNS = [
  '文件名称',
  '文件级别',
  '公文种类',
  '主题分类',
  '国家级文件名称',
  '市级省级文件名称',
  '区级县级文件名称',
  '责任机构或人',
  '具体事权',
  '具体面向对象',
  '必要条件',
  '管理标准',
  '审核过程',
  '施行时间',
  '继承关系',
  '联系',
  '关联内容',
  '变动',
  '推行和改革要求',
  '实施内容',
  '对应群体',
  '对应区域',
  '对应方向',
  '对应经济文化',
  '附件',
]

/** RFC4180 风格转义，与 Python csv 兼容 */
function escapeCsvField(val) {
  const s = String(val ?? '')
  if (/[",\r\n]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`
  }
  return s
}

/**
 * 生成与 policyexplain.csv 同结构的文本（可含表头 + 多行数据）。
 * @param {Array<Record<string, string>>} rows
 */
export function buildPolicyExplainCsvText(rows) {
  const header = POLICY_EXPLAIN_CSV_COLUMNS.map(escapeCsvField).join(',')
  const lines = [header]
  for (const row of rows) {
    const line = POLICY_EXPLAIN_CSV_COLUMNS.map((k) =>
      escapeCsvField(row[k] != null && row[k] !== '' ? row[k] : '无'),
    ).join(',')
    lines.push(line)
  }
  return `${lines.join('\r\n')}\r\n`
}

export function downloadPolicyExplainCsv(filename, rows) {
  const text = buildPolicyExplainCsvText(rows)
  const blob = new Blob(['\uFEFF', text], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
