# @nomadamas/k-skill

## 0.2.1

### Patch Changes

- Bundle and migrate the remaining fine-dust, KTX, and setup root helpers found
  by the registry E2E suite.

## 0.2.0

### Minor Changes

- c556b5e: k-skill 통합 CLI를 추가하고 122개 스킬 전체를 runtime-aware adapter로 전환한다.
  generic/Dolshoi instruction 조립(`instruct`), 82개 helper script 실행(`exec`),
  8개 reference 조회(`read`), 안전한 asset 경로 확인(`path`), 전체 목록(`list`)을
  제공하며 모든 bundled asset을 npm 패키지에 포함한다.
