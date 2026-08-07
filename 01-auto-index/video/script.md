# 01 녹화 대본

## 사전 준비

- 화면 녹화 = `⌘⇧5` → 선택 범위. **1280x720 이상**
- 터미널 폰트를 **16pt 이상**으로. 축소되면 안 보인다
- 터미널·에디터 모두 **다크 테마**로 통일
- 마우스 이동을 최소화한다. 산만해진다
- **컷마다 파일을 나눈다.** 아래 파일명 그대로 저장

작업 디렉터리

    /Users/jacepark/ShortForm/jacepark-lab/01-auto-index

녹화 전 초기화

    rm -rf output demo.py

**각 컷은 최소 20초 확보한다.** 나레이션보다 크게 짧으면 정지 화면이
길어진다. 길면 합성 스크립트가 배속으로 맞춘다.

---

## 01_problem.mov — 문제를 보여준다

**화면** 에디터. `posts/` 폴더가 사이드바에 펼쳐진 상태

1. `posts/a1.html` 을 연다 — 3초 정지
2. `posts/a2.html` 을 연다 — 3초 정지
3. `posts/a3.html` 을 연다 — 3초 정지
4. `posts/a4.html` 을 연다 — 3초 정지
5. `posts/a5.html` 을 연다 — 3초 정지
6. 그대로 5초 정지

**의도** 기사가 여러 개라는 것만 전달한다. 내용은 읽히지 않아도 된다

---

## 02_meta.mov — 메타 블록을 보여준다

**화면** `posts/a1.html` 만. 확대해서 글자가 크게 보이게

1. 메타 블록 전체(1~7행)를 마우스로 드래그 선택 — 3초 정지
2. 선택 유지 — 6초 정지
3. `tags:` 행만 다시 드래그 선택 — 3초 정지
4. 선택 유지 — 6초 정지

**의도** `tags` 한 줄이 이 구조의 전부라는 것

---

## 03_write.mov — 코드를 친다

**화면** 터미널 → 에디터

1. 터미널에서 `touch demo.py` 실행
2. 에디터에서 `demo.py` 를 연다 (빈 파일)
3. 아래를 **직접 타이핑한다.** 붙여넣기 금지 — 치는 그림이 필요하다

        import re
        from pathlib import Path

        META = re.compile(r"<!--META\s*(.*?)-->", re.DOTALL)

        for path in sorted(Path("posts").glob("*.html")):
            m = META.search(path.read_text())
            print(path.name, "->", m.group(1).strip()[:30] if m else "なし")

4. 저장 — 3초 정지

**의도** 메타 블록을 뽑는 부분만 손으로 만든다. 전체를 다 치지 않는다

**주의** 평소보다 천천히 친다. 빠르면 나레이션보다 짧아진다

---

## 04_run_fail.mov — 불완전한 성공

**화면** 터미널

1. `python3 demo.py` 실행
2. 결과가 나온다 — 파일명과 메타 앞부분만 찍힌다
3. 8초 정지

**의도** 에러가 아니라 **뽑기는 했는데 이대로는 못 쓴다**를 보인다

---

## 05_real_run.mov — 완성본을 돌린다

**화면** 터미널

1. `python3 build_index.py posts` 실행
2. 집계가 나온다

        ○ automation        3 件
        － ffmpeg            2 件
        － python            2 件

3. **12초 정지.** 여기가 이 영상의 핵심 화면이다

**의도** `○` 와 `－` 의 차이를 읽게 한다. 서두르지 않는다

---

## 06_build.mov — 생성한다

**화면** 터미널 → 에디터

1. `python3 build_index.py posts --build` 실행
2. `生成: output/automation.html (3 件)` — 4초 정지
3. 에디터에서 `output/automation.html` 을 연다
4. 표 부분이 보이게 — 8초 정지

**의도** 결과물이 실제로 나온다는 것

---

## 07_cleanup.mov — 마무리

**화면** 터미널

1. `rm demo.py` 실행
2. `ls` 실행 — 정리된 상태를 보인다
3. 8초 정지

**의도** 실습 파일을 지우고 영상 안에서 끝맺는다

---

## 녹화 후

아래 위치에 파일명 그대로 넣는다.

    01-auto-index/video/recordings/
    ├─ 01_problem.mov
    ├─ 02_meta.mov
    ├─ 03_write.mov
    ├─ 04_run_fail.mov
    ├─ 05_real_run.mov
    ├─ 06_build.mov
    └─ 07_cleanup.mov

`recordings/` 는 저장소에 올리지 않는다.
