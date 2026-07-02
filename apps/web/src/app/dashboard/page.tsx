import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  { db: { schema: 'localize' } }
)

async function getDashboardData() {
  const { data: persons } = await supabase
    .from('persons')
    .select('last_known_location, status, created_at, updated_at')

  return { persons: persons ?? [] }
}

type Person = {
  last_known_location: string | null
  status: string
  created_at: string
  updated_at: string
}

function calcZoneStats(records: Person[]) {
  const zones: Record<string, { total: number; found: number }> = {}
  for (const r of records) {
    const z = r.last_known_location ?? 'Sin ubicación'
    if (!zones[z]) zones[z] = { total: 0, found: 0 }
    zones[z].total++
    if (r.status === 'found') zones[z].found++
  }
  return Object.entries(zones)
    .map(([zone, s]) => ({
      zone,
      total: s.total,
      found: s.found,
      missing: s.total - s.found,
      pct: Math.round((s.found / s.total) * 100),
    }))
    .sort((a, b) => b.missing - a.missing)
}

export default async function PulsoDashboard() {
  const { persons } = await getDashboardData()
  const total = persons.length
  const found = persons.filter((r) => r.status === 'found').length
  const missing = persons.filter((r) => r.status !== 'found').length
  const pctFound = total > 0 ? Math.round((found / total) * 100) : 0
  const zones = calcZoneStats(persons)

  const foundPersons = persons.filter((r) => r.status === 'found')
  const avgDays =
    foundPersons.length > 0
      ? Math.round(
          foundPersons.reduce((acc, r) => {
            const diff =
              (new Date(r.updated_at).getTime() - new Date(r.created_at).getTime()) /
              (1000 * 60 * 60 * 24)
            return acc + diff
          }, 0) / foundPersons.length
        )
      : null

  return (
    <main className="min-h-screen bg-canvas px-6 py-12 font-sans">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        <div className="mb-10">
          <span className="text-[11px] font-semibold tracking-[0.88px] uppercase text-muted">
            Localizalo · Dashboard
          </span>
          <h1 className="mt-2 text-[36px] font-semibold leading-[1.15] tracking-[-1.08px] text-ink">
            Pulso
          </h1>
          <p className="mt-2 text-body text-base">
            Vista en tiempo real del estado de la búsqueda: zonas críticas, velocidad de resolución y personas sin encontrar.
          </p>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
          <div className="bg-surface-card border border-hairline-strong rounded-xl p-6">
            <p className="text-[11px] font-semibold tracking-[0.88px] uppercase text-muted mb-2">
              Total registradas
            </p>
            <p className="text-[48px] font-semibold leading-none tracking-[-1.44px] text-ink">
              {total.toLocaleString('es')}
            </p>
          </div>

          <div className="bg-surface-card border border-hairline-strong rounded-xl p-6">
            <p className="text-[11px] font-semibold tracking-[0.88px] uppercase text-muted mb-2">
              Encontradas
            </p>
            <p className="text-[48px] font-semibold leading-none tracking-[-1.44px] text-success">
              {pctFound}%
            </p>
            <p className="text-sm text-body mt-1">{found.toLocaleString('es')} personas</p>
          </div>

          <div className="bg-surface-card border border-hairline-strong rounded-xl p-6">
            <p className="text-[11px] font-semibold tracking-[0.88px] uppercase text-muted mb-2">
              Sin encontrar
            </p>
            <p className="text-[48px] font-semibold leading-none tracking-[-1.44px] text-error">
              {missing.toLocaleString('es')}
            </p>
            {avgDays !== null && (
              <p className="text-sm text-body mt-1">Resolución promedio: {avgDays}d</p>
            )}
          </div>
        </div>

        {/* Zone Table */}
        <div className="bg-surface-card border border-hairline-strong rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-hairline">
            <h2 className="text-[18px] font-semibold text-ink">Zonas con mayor déficit</h2>
            <p className="text-sm text-body mt-0.5">Ordenadas por personas sin encontrar</p>
          </div>
          <div className="divide-y divide-hairline">
            {zones.slice(0, 15).map((z) => (
              <div key={z.zone} className="px-6 py-4 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-ink truncate">{z.zone}</p>
                  <p className="text-xs text-body mt-0.5">{z.total} registradas</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-32 h-1.5 bg-surface-strong rounded-full overflow-hidden">
                    <div
                      className="h-full bg-success rounded-full"
                      style={{ width: `${z.pct}%` }}
                    />
                  </div>
                  <span className="text-xs font-semibold text-success w-10 text-right">
                    {z.pct}%
                  </span>
                  <span className="text-xs text-error font-semibold w-16 text-right">
                    -{z.missing} falt.
                  </span>
                </div>
              </div>
            ))}
            {zones.length === 0 && (
              <div className="px-6 py-8 text-center text-body text-sm">
                No hay datos disponibles aún.
              </div>
            )}
          </div>
        </div>

        <p className="mt-6 text-xs text-muted text-center">
          Datos actualizados cada 10 minutos · Localizalo {new Date().getFullYear()}
        </p>
      </div>
    </main>
  )
}