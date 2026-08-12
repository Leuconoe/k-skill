# SRT 라이브 시간표 조회 가이드

`srt-booking`은 `SRTrain`의 시간표 검색 경로를 사용해 현재 SRT 운행 시각과 일반실·특실 가능 여부를 조회하는 **라이브 조회 전용** 스킬이다.

## 제공하는 정보

- 현재 열차번호
- 출발·도착 시각
- 일반실·특실 예약 가능 여부
- 공식 SRT 페이지

## 제공하지 않는 기능

- 회원 로그인과 credential 불필요
- 예약·예약대기·결제·취소 없음
- 호차·좌석번호 선택
- 자동 재조회·매진 감시

```bash
npx -y @nomadamas/k-skill@0 exec srt-booking scripts/srt_booking.py -- \
  search --dep 수서 --arr 부산 --date 20260819 --time 0600 --time-limit 1200 --limit 5
```

조회 transport:

```bash
npx -y @nomadamas/k-skill@0 exec srt-booking scripts/srt_booking.py -- source
```

## 구현 경계

- `SRT("", "", auto_login=False)`로 로그인 없이 조회한다.
- NetFunnel 대기열 처리 후 `selectListAra10007_n.do` 시간표 검색만 호출한다.
- `available_only=False`로 매진 열차도 함께 받아 현재 좌석 상태를 표시한다.
- 예약·결제·취소 endpoint는 호출하지 않는다.
- 오류나 접근 제한이 발생하면 우회하지 않고 공식 페이지를 안내한다.

상세 위험 고지: [`AUTOMATION-LEGAL-STATEMENT.md`](../../srt-booking/references/AUTOMATION-LEGAL-STATEMENT.md)
