# KTX 공식 시간표 조회 가이드

`ktx-booking`은 한국철도공사가 공개하는 최신 KTX 운행시간표 XLSX를 읽어 출발역·도착역·출발시간에 맞는 열차를 찾는 조회 전용 스킬이다.

회원 로그인과 credential은 사용하지 않는다.

## 제공하는 정보

- 계획 시간표상의 열차번호·열차종류
- 요청 역 사이의 출발·도착 시각
- 적용된 공식 게시물과 XLSX 출처
- 공식 코레일 예매 페이지

## 제공하지 않는 정보

- 실시간 잔여석은 조회하지 않는다.
- 실시간 일반실·특실 잔여석
- 실제 운휴·지연
- 호차·좌석번호
- 예약·예약대기·결제·취소는 실행하지 않는다.

```bash
npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/ktx_booking.py -- \
  search --dep 서울 --arr 부산 --date 20260819 --time 0600 --time-limit 1200 --limit 5
```

```bash
npx -y @nomadamas/k-skill@0 exec ktx-booking scripts/ktx_booking.py -- source
```

결과는 코레일의 공식 계획 시간표다. 실제 이용 전에는 공식 예매 페이지에서 운휴·지연과 잔여석을 다시 확인해야 한다.
