# KTX 라이브 시간표 조회 가이드

`ktx-booking`은 `korail2`의 시간표 검색 경로를 사용해 현재 KTX 운행 시각과 일반실·특실 가능 여부를 조회하는 **라이브 조회 전용** 스킬이다.

## 제공하는 정보

- 현재 열차번호·열차종류
- 요청 역 사이의 출발·도착 시각
- 일반실·특실 예약 가능 여부
- 공식 코레일 페이지

## 제공하지 않는 기능

- 회원 로그인과 credential 불필요
- 예약·예약대기·결제·취소 없음
- 호차·좌석번호 선택
- 자동 재조회·매진 감시

```bash
npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/ktx_booking.py -- \
  search --dep 서울 --arr 부산 --date 20260819 --time 0600 --time-limit 1200 --limit 5
```

조회 transport:

```bash
npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/ktx_booking.py -- source
```

## 구현 경계

- `Korail("", "", auto_login=False)`로 로그인 없이 조회한다.
- 호출 endpoint는 `ScheduleView` 시간표 검색으로 제한한다.
- 순정 `korail2==0.4.0`이 현재 코레일 Dynapath 검사에서 `MACRO ERROR`를 반환하므로, Dynapath search header를 지원하는 고정 revision을 사용한다.
- 인접역 후보가 포함될 수 있어 요청 출발역·도착역과 정확히 일치하는 결과만 표시한다.
- 오류나 접근 제한이 발생하면 우회하지 않고 공식 페이지를 안내한다.

상세 위험 고지: [`AUTOMATION-LEGAL-STATEMENT.md`](../../ktx-booking/references/AUTOMATION-LEGAL-STATEMENT.md)
