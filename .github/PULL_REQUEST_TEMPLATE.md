# 📋 Pull Request

> PRs neste projeto seguem este template. Marque tudo que se aplica.

## 🎯 O que muda?

<!-- Resumo em 1-2 frases do que este PR entrega -->

## 🔗 Issue / Work item relacionada

<!-- Link para Jira, Azure Boards ou GitHub Issue -->

## 🏷️ Tipo de mudança

- [ ] ✨ Feature (nova medida, nova tabela, novo visual)
- [ ] 🐛 Fix (correção de bug ou regra de negócio)
- [ ] ♻️ Refactor (sem mudança de comportamento)
- [ ] ⚡ Performance (otimização de medida, redução de tempo de refresh)
- [ ] 📚 Docs (apenas documentação)
- [ ] 🔒 Security (RLS, permissões, dados sensíveis)
- [ ] 🧹 Chore (manutenção, dependências, CI)

## 🧪 Como foi testado?

- [ ] DAX smoke tests atualizados
- [ ] Testado em workspace Dev
- [ ] Testado em workspace Test
- [ ] Validado com owner do domínio

## 📊 Impacto

- **Datasets afetados:** <!-- listar -->
- **Reports afetados:** <!-- listar -->
- **RLS alterado?** <!-- sim/não, justificar -->
- **Refresh impactado?** <!-- sim/não, justificar -->
- **Compatibilidade com versões anteriores?** <!-- sim/não -->

## 📸 Evidências (se UI)

<!-- Screenshots, GIFs, vídeos -->

## 📚 Documentação

- [ ] `docs/data-dictionary.md` atualizado
- [ ] `docs/naming-conventions.md` respeitado
- [ ] Comentários no TMDL adicionados
- [ ] CHANGELOG atualizado

## ✅ Checklist do autor

- [ ] Branch segue convenção (`feat/`, `fix/`, `refactor/`, etc.)
- [ ] Commits seguem Conventional Commits
- [ ] Build local verde (`scripts/compile-pbip.ps1`)
- [ ] Self-review do próprio código
- [ ] Sem dados sensíveis commitados

## 👥 Reviewers sugeridos

<!-- @mention dos revisores por área -->

- [ ] @tech-lead
- [ ] @analytics-engineer
- [ ] @steward-dados (se houver mudança de modelo)
- [ ] @qa (se houver mudança de UI/report)

## 🚀 Plano de release

<!-- Como será feita a promoção após merge -->

- [ ] Deploy Dev automático (merge em main)
- [ ] Promoção Test após QA sign-off
- [ ] Promoção Prod após steward sign-off
