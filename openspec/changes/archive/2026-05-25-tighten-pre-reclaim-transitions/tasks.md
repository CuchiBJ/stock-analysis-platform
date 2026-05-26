## 1. Editar los 4 blocks en transition_engine.py [transition-engine]

- [ ] 1.1 Block #4 FLUSH_AND_RECOVER: agregar `self._is_quality_leader(current_metrics) and`
- [ ] 1.2 Block #5 VOLUME_DRY_UP: agregar quality gate + cambiar `ema21 < -0.3` por `-2.0 <= ema21 < -0.3`
- [ ] 1.3 Block #6 COMPRESSING: agregar quality gate + cambiar `ema21 < -0.3` por `-2.0 <= ema21 < -0.3`
- [ ] 1.4 Block #8 SUPPORT_HOLDING: agregar quality gate + agregar `ema21 < 0`

## 2. Validación [transition-engine]

- [ ] 2.1 Verificar que ALM, CLS (volume_dry_up) y AMKR, ICHR, MTZ (compressing) siguen apareciendo en el feed — son líderes legítimos
- [ ] 2.2 Confirmar que el feed no queda vacío
- [ ] 2.3 Buscar un stock con `distance_to_ema21_atr < -2.0` y confirmar que no dispara VOLUME_DRY_UP ni COMPRESSING
