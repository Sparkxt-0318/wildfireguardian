# `rescue_baseline_synthetic/` — synthetic road-network baseline (self-correction record)

이 디렉터리는 합성 도로망 기준의 초기 baseline입니다(N=452, w≈40%). 정본은 상위
`data/processed/` 의 동명 파일이며 실제 OpenStreetMap 도로망 기준입니다(N=439, w≈11%).
두 실행은 자기수정 기록으로 함께 보존됩니다.

---

The canonical `rescue_*.json` files are the copies in the parent `data/processed/` directory
(real OpenStreetMap road network). The copies here are the earlier synthetic-grid baseline,
retained deliberately so the correction is auditable. Selection depends on **path**, not
filename — do not cite the files in this directory as canonical.
