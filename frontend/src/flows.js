export function observedMonths(history = [], cutoff) {
  const supplied = history.filter(r => /^\d{4}-\d{2}-\d{2}$/.test(r.snapshot_month || '') && (!cutoff || r.snapshot_month <= cutoff))
    .toSorted((a,b)=>a.snapshot_month.localeCompare(b.snapshot_month));
  if (!supplied.length) return [];
  const monthIndex = value => { const [y,m] = value.split('-').map(Number); return y*12+m-1; };
  const last = monthIndex(cutoff || supplied.at(-1).snapshot_month);
  const first = Math.max(monthIndex(supplied[0].snapshot_month),last-11);
  const byMonth = new Map(supplied.map(r=>[r.snapshot_month.slice(0,7),r]));
  return Array.from({length:last-first+1},(_,i)=>{
    const index=first+i, year=Math.floor(index/12), month=index%12;
    const snapshot_month=new Date(Date.UTC(year,month+1,0)).toISOString().slice(0,10);
    return byMonth.get(snapshot_month.slice(0,7)) || {snapshot_month};
  });
}
