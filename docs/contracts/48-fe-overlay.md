# Контракт #48: video overlay

Issue: https://github.com/ne5ermind/traffic-analysis/issues/48

Canvas запрашивает detections по `player.currentTime` и рисует нормализованный `box` относительно фактической области кадра с учётом `object-fit: contain`.

Показываются категория и tracker ID; линии/ROI могут отображаться вместе с bbox. `objects=[]`, seek и смена run очищают старые рамки. Ответ старого запроса игнорируется. Overlay не блокирует controls видео.

