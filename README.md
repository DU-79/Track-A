# 璧涢亾 A锛欵DA 杞欢

> 鍙傝禌闃熶紞閫夋嫨鏈禌閬撳悗瀹屾垚 **A1 + A2 + A3 鍏ㄩ儴棰樼洰**銆�
> 鏈禌閬撹嚜鐮斿伐鍏峰皢涓鸿禌閬� B 鐨� RTL 浠ｇ爜鎻愪緵浠跨湡銆侀獙璇佷笌缁煎悎 PPA 璇勪及鏈嶅姟銆�

## 璧涢鍒楄〃

| 缂栧彿 | 璧涢 | 璧涢璇存槑 | 璇勫垎缁嗗垯 | 鍏紑娴嬭瘯闆� |
|------|------|----------|----------|-----------|
| A1 | 杞婚噺 RTL 浠跨湡鍣� | [spec.md](A1-simulator/spec.md) | [scoring.md](A1-simulator/scoring.md) | [testcases/](A1-simulator/testcases/) |
| A2 | 楠岃瘉鐜鑷姩鐢熸垚 | [spec.md](A2-verification/spec.md) | [scoring.md](A2-verification/scoring.md) | [testcases/](A2-verification/testcases/) |
| A3 | 杞婚噺 RTL 閫昏緫缁煎悎宸ュ叿 | [spec.md](A3-synthesis/spec.md) | [scoring.md](A3-synthesis/scoring.md) | [testcases/](A3-synthesis/testcases/) |

## 璧涢亾鎬昏

璧涢亾 A 鑱氱劍浜�**鑷爺 EDA 宸ュ叿**锛屽寘鍚笁涓嫭绔嬭瘎鍒嗙殑瀛愰锛�

```text
A1 浠跨湡鍣�        -> 涓鸿禌閬� B 鎻愪緵杞婚噺绾� RTL 浠跨湡鑳藉姏
A2 楠岃瘉鐢熸垚鍣�    -> 涓鸿禌閬� B 鑷姩鐢熸垚楠岃瘉鐜
A3 閫昏緫缁煎悎宸ュ叿  -> 涓鸿禌閬� B 鎻愪緵 PPA 璇勪及鍙嶉
```

## 璇勫垎鎬诲垯

**璧涢亾 A 鍒嗕负 A1銆丄2銆丄3 涓夐亾璧涢锛屾瘡閬撳師濮嬫弧鍒嗗潎涓� 100 鍒嗐€傛渶缁堣禌閬撴€诲垎涓轰笁閬撻褰掍竴鍖栧悗绛夋潈骞冲潎锛屾弧鍒嗕负 100 鍒嗐€�**

```text
璧涢亾鎬诲垎 = (A1褰掍竴鍖栧垎 + A2褰掍竴鍖栧垎 + A3褰掍竴鍖栧垎) / 3
A1褰掍竴鍖栧垎 = (A1鍘熷寰楀垎 / 100) x 100
A2褰掍竴鍖栧垎 = (A2鍘熷寰楀垎 / 100) x 100
A3褰掍竴鍖栧垎 = (A3鍘熷寰楀垎 / 100) x 100
```

> **绀轰緥**锛欰1 寰� 70 鍒嗐€丄2 寰� 80 鍒嗐€丄3 寰� 60 鍒嗭紝鍒欒禌閬撴€诲垎 = (70 + 80 + 60) / 3 = 70 鍒嗐€�

| 璧涢 | 鍘熷婊″垎 | 璇勫垎鏋勬垚 |
|------|----------|----------|
| A1 杞婚噺 RTL 浠跨湡鍣� | 100 | 璇█瑙ｆ瀽 (F1) + 姝ｇ‘鎬� (F2) + 缂栬瘧鎬ц兘 (P1) + 浠跨湡鎬ц兘 (P2) + 澶氭牳鍔犻€熸瘮 (P3) |
| A2 楠岃瘉鐜鑷姩鐢熸垚 | 100 | 10 鐢佃矾 x 10 鍒嗭紙楠ㄦ灦 3 + 瑕嗙洊鐜� 7锛� |
| A3 閫昏緫缁煎悎宸ュ叿 | 100 | PPA Hypervolume 90 + Runtime 5 + 鍘熷垱鎬� 5 |

## 鎻愪氦瑙勮寖

| 瀛愰 | 蹇呬氦鏂囦欢 |
|------|----------|
| A1 | `Makefile` + 浠跨湡鍣ㄦ簮鐮� |
| A2 | `run.sh` 鎴� `run.py` + 婧愮爜 + `requirements.txt` |
| A3 | `Makefile` + `submission.yaml` + `config.json` + `ORIGINALITY_DECLARATION.md` + `THIRD_PARTY.md` + `src/` |

## 鐜绾︽潫

| 瀛愰 | 鐜 |
|------|------|
| A1 | Linux x86_64锛岃瘎娴嬬郴缁熸彁渚� filelist |
| A2 | Linux x86_64锛孭ython 3.10+锛屽厑璁� Z3/PyVerilog |
| A3 | 鍐荤粨 Docker 闀滃儚 `my_siliconcompiler_image:latest`锛孻osys 0.54 / OpenSTA 2.7.0 / Icarus 10.3 |
