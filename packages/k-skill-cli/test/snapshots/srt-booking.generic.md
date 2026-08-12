# srt-booking — assembled instructions

Runtime mode: generic

## Runtime rules

- Detect capabilities, not product names. Dolshoi credential mode is active only when `DOLSHOI_ACTION_BROKER_URL` is set and `vault-run` is available; CloakBrowser mode is active when the built-in browser tool identifies CloakBrowser or `CLOAKBROWSER_PEEK_TOKEN` is set.
- When the user asks for an action and the official surface supports it lawfully, continue beyond lookup through reversible preparation and execution. Do not declare completion at a result list, deep link, or handoff when the action can still be carried out.
- Immediately before an irreversible external side effect such as payment, message/email delivery, final submission, cancellation, account mutation, or public posting, call `clarify` with the exact target, amount/payload, and effect. Execute only after approval; do not ask again for already-approved reversible steps.
- Preserve hard boundaries for law, required physical presence, CAPTCHA, identity proofing, electronic signatures, and unsupported official surfaces. In those cases, complete the furthest lawful supported step and open or prepare the exact next official step for the user.

## Bundled asset access

- Execute bundled helpers only through `npx -y @nomadamas/k-skill@0 exec srt-booking scripts/<file> -- <args>`; do not assume a repository-relative or installed-skill-relative path.
- Resolve an asset path with `npx -y @nomadamas/k-skill@0 path srt-booking <relative-path>` only when another tool explicitly requires a filesystem path.
- Read bundled references through `npx -y @nomadamas/k-skill@0 read srt-booking references/<file>`.

# SRT Timetable Lookup

## What this skill does

주식회사 에스알이 로그인 없이 공개하는 최신 SRT 운행시각표 HWP를 내려받아 `kordoc`으로 임시 변환하고, 출발역·도착역·출발시간 조건에 맞는 열차를 찾는다.

이 스킬은 **조회 전용**이다.

- 회원 로그인, 자격증명, SRTrain 또는 SRT 내부 예약 API를 사용하지 않는다.
- 실시간 잔여석, 호차별 좌석번호, 예약 상태를 조회하지 않는다.
- 예약, 예약대기, 결제, 취소, 자동 재조회 또는 좌석 선점을 실행하지 않는다.
- 결과에는 사용자가 직접 확인할 SRT 공식 예매 페이지 링크만 제공한다.

공개 운행시각표는 계획 시각표다. 실제 운휴·지연·편성 변경과 좌석 판매 상태는 공식 SRT 페이지에서 사용자가 직접 확인해야 한다.

## Commands

실행 전 helper 위치를 확인한다.

```bash
npx -y @nomadamas/k-skill@0 files srt-booking
```

### 시간표 조회

```bash
npx -y @nomadamas/k-skill@0 exec srt-booking scripts/srt_booking.py -- \
  search \
  --dep 수서 \
  --arr 부산 \
  --date 20260820 \
  --time 0600 \
  --time-limit 1200 \
  --limit 10
```

입력:

- `--dep`: 출발역 이름
- `--arr`: 도착역 이름
- `--date`: `YYYYMMDD`
- `--time`: 가장 이른 출발시각 `HHMM`
- `--time-limit`: 가장 늦은 출발시각 `HHMM`
- `--limit`: 최대 결과 수, 1–50

출력:

- `trains[].train_no`
- `trains[].dep`, `trains[].arr`
- `trains[].dep_time`, `trains[].arr_time`
- `source.title`, `source.effective_date`, `source.download_url`
- `booking_url`
- `schedule_note`

### 현재 공식 원본 확인

```bash
npx -y @nomadamas/k-skill@0 exec srt-booking scripts/srt_booking.py -- source
```

## Workflow

1. 사용자가 출발역, 도착역, 날짜와 희망 시간대를 주지 않았다면 필요한 값만 확인한다.
2. `search`를 정확히 한 번 실행한다.
3. 운행 후보와 공식 원본 기준일을 함께 보여준다.
4. 좌석 구매가 필요하면 `booking_url`을 제공하고 종료한다.
5. 결과가 없으면 역명·시간대를 확인하되 자동 polling 또는 반복 감시를 시작하지 않는다.

## Hard boundaries

- `KSKILL_SRT_ID`, `KSKILL_SRT_PASSWORD` 또는 다른 회원 credential을 요구하지 않는다.
- `SRTrain`, 비공개 앱 API 또는 좌석선택 내부 endpoint를 사용하지 않는다.
- 예약·예약대기·결제·취소·승차권 변경을 지원한다고 표현하지 않는다.
- CAPTCHA, anti-bot, 접근 제한 또는 차단을 우회하지 않는다.
- 사용자의 한 번의 질문을 장기 실행 감시나 반복 요청으로 확장하지 않는다.
- 공개 시간표에 없는 좌석·판매상태·지연정보를 추측하지 않는다.

## Temporary document handling

- 공식 HWP 첨부는 임시 디렉터리에만 저장한다.
- `npx -y kordoc`으로 Markdown을 만든 뒤 helper 종료 시 HWP와 Markdown을 함께 삭제한다.
- 원문이나 변환물을 credential 저장소, repository 또는 장기 cache에 보관하지 않는다.

## Failure modes

- 에스알 공식 시간표 게시판 또는 첨부 파일 접근 실패
- `npx` 또는 `kordoc`을 실행할 수 없음
- HWP 형식 변경으로 Markdown 변환 실패
- 입력한 역이 최신 공개 시간표에 없음
- 날짜·시간 형식 오류
- 조건에 맞는 계획 열차 없음

이 경우 오류를 그대로 설명하고 [SRT 공식 예매 페이지](https://etk.srail.kr/hpg/hra/01/selectScheduleList.do?pageId=TK0101010000)에서 직접 확인하도록 안내한다.

## Notes

- 법적·약관상 배경은 다음 명령으로 읽는다.

```bash
npx -y @nomadamas/k-skill@0 read srt-booking references/AUTOMATION-LEGAL-STATEMENT.md
```
- 이 스킬이 조회하는 것은 공개 운행계획이며 실시간 예약 가능 좌석이 아니다.
