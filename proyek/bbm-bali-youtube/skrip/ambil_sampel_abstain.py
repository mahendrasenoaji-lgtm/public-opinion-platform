import csv, random, sys, json
rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8-sig')))
ab = [r for r in rows if r['sentiment_label'] == 'abstain']
random.seed(20261106)
s = random.sample(ab, 400)
out = [{'i': k + 1, 'id': r['comment_id'], 'text': ' '.join(r['text'].split())[:240]} for k, r in enumerate(s)]
json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False)
lo, hi = int(sys.argv[3]), int(sys.argv[4])
for o in out[lo:hi]:
    print(o['i'], '|', o['text'])
