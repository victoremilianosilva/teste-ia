# Validação do sistema de itens — Fase 6

Esta fase valida separadamente o contrato dos itens, o caminho nativo, a integração com PPO e os resultados de política. Não considerar a fase concluída apenas porque testes unitários passaram.

## 1. Testes unitários e de contrato

Na raiz do repositório:

```bash
python -m pytest tests/test_ppo_mask_consistency.py tests/test_viewer_items.py tests/test_evaluate_checkpoints.py -q
```

No build C++ já configurado:

```bash
ctest --test-dir cpp/build --output-on-failure -R 'item_engine|test_reward_model'
```

Esses testes verificam receitas/inventário/equipamento, os contratos de ação 7/8, máscaras e log-probabilidades PPO, recompensa estratégica e métricas de avaliação.

## 2. Integração nativa

Recompile o módulo nativo usando o procedimento normal do projeto e rode os testes CTest acima. A validação precisa passar pelo CppTFTLobbyWrapper real, não apenas por mocks. Se o módulo não estiver compilado ou o catálogo real não estiver disponível, registrar como bloqueio; não contabilizar como teste aprovado.

## 3. Comparação antes/depois do treinamento

Use dois checkpoints compatíveis com a mesma versão da policy e da engine: um baseline anterior ao treinamento com a recompensa estratégica e outro treinado com ela. Use as mesmas seeds e o mesmo número de partidas:

```bash
python scripts/evaluate_checkpoints.py \
  --baseline checkpoints/baseline.pt \
  --candidate checkpoints/items_phase5.pt \
  --matches 40 \
  --output reports/items_phase6_head_to_head.csv
```

O avaliador produz resultados por jogador e resumo pareado de colocação média, taxa de vitória, top 4 e intervalos bootstrap por seed. Também registra ações totais, ações de item, equipagens e combinações/equipagens, para evitar interpretar uma melhora de colocação sem saber se a policy realmente utilizou o sistema de itens.

## 4. Como interpretar

- Comparar colocação média (menor é melhor), taxa de vitória e top 4.
- Verificar se as ações de item são válidas e se a policy realmente equipou ou combinou itens.
- Inspecionar deltas por seed e intervalo bootstrap; não afirmar causalidade com poucas partidas ou checkpoints treinados em condições diferentes.
- Guardar CSV, checkpoints, commit da engine, seeds, configuração de treino e logs TensorBoard junto ao relatório.
- Se não houver checkpoint baseline e checkpoint treinado comparáveis, marcar a avaliação de resultados como pendente; não inventar métricas antes/depois.

## 5. Limites conhecidos

O catálogo sintético de testes não é um catálogo completo de um set de TFT. Os efeitos de itens que a engine de combate não simula não devem ser tratados como validados. Testes de integração comprovam o caminho de execução, mas só um experimento com checkpoints treinados e partidas pareadas pode medir o impacto estratégico.
