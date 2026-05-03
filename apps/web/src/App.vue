<template>
  <main class="shell">
    <section class="panel">
      <header class="panel__header">
        <div>
          <p class="eyebrow">Little Bear</p>
          <h1>问答前端骨架</h1>
        </div>
        <span class="badge">Vue 3</span>
      </header>

      <div class="grid">
        <article class="card">
          <h2>当前范围</h2>
          <p>终端用户页面壳、API 接入位置、后续查询工作区入口。</p>
        </article>
        <article class="card">
          <h2>后续对接</h2>
          <p><code>/internal/v1/queries</code>、知识库浏览、登录态与 citation 展示。</p>
        </article>
      </div>
    </section>
  </main>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  background: #f4f7fb;
  color: #122033;
  padding: 32px;
}

.panel {
  max-width: 1080px;
  margin: 0 auto;
}

.panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  text-transform: uppercase;
  color: #5f728c;
}

h1 {
  margin: 0;
  font-size: 32px;
}

.badge {
  border: 1px solid #c7d4e5;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  background: #fff;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.card {
  background: #fff;
  border: 1px solid #dbe5f0;
  border-radius: 8px;
  padding: 20px;
}

h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

p {
  margin: 0;
  line-height: 1.6;
}

code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}
</style>
