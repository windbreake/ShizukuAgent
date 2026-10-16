<template>
  <section class="adapter-logs-page">
    <article class="panel adapter-logs-card">
      <h1>Adapter 日志</h1>
      <p>
        如果需要查看实时日志，请切换到控制面板中的“系统日志”，或通过
        <code>/api/adapter_logs</code>
        接口获取内容。
      </p>
      <RouterLink class="btn ghost" to="/logs"><UiIcon name="logs"/>打开日志页面</RouterLink>
    </article>
  </section>
</template>
