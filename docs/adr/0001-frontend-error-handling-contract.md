# 前端错误提示由拦截器统一负责

`src/api/index.ts` 的 axios 响应拦截器**已经**对所有失败请求弹 `ElMessage.error` 并 `Promise.reject()`。因此业务代码不得再对同一个错误二次弹窗，也不得写 `if (res.data.code === 200)` 的成功判断——代码能 resolve 就说明一定成功，那个 `else` 分支永不执行。

**Status**: accepted

## Considered Options

1. **集中处理（选此方案）**：拦截器统一弹错，业务代码只写成功路径，catch 里最多 `console.error` 留排查线索。
2. **各处自行处理**：每个调用点自己判断 `code` 并弹错。原代码是这个模式，导致拦截器弹一次、业务再弹一次，同一个错误出现两条提示。
3. **拦截器静默，全交给业务**：业务代码变每个调用点都要判 `code`，样板膨胀且容易漏写，漏写即错误被静默吞掉。

## Consequences

- 业务 `catch` 块里出现 `console.error` 而**不**弹窗，是**有意为之**，不是遗漏。后续如需接入前端错误上报（如 Sentry），这些 `console.error` 就是统一改为上报调用的挂载点。
- 少数 `catch` 承接的是非请求失败（如 `ElMessageBox.confirm` 的用户取消、`formRef.validate()` 的校验失败），这些保留原有注释语义，不属于本契约范围。
- 若将来某个接口需要**覆盖**默认提示（例如用更友好的文案），应在拦截器层按接口配置，而不是在业务层补弹。
