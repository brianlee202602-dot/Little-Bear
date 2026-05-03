<template>
  <main class="shell">
    <section class="layout">
      <aside class="sidebar">
        <p class="brand">Little Bear Admin</p>
        <nav class="nav">
          <a href="#">导入任务</a>
          <a href="#">知识库</a>
          <a href="#">用户与部门</a>
          <a href="#">角色权限</a>
          <a href="#">配置中心</a>
          <a href="#">审计中心</a>
        </nav>
      </aside>

      <section class="content">
        <header class="content__header">
          <div>
            <p class="eyebrow">管理后台骨架</p>
            <h1>后台管理页面壳</h1>
          </div>
          <span class="badge">Vue 3</span>
        </header>

        <div class="cards">
          <article class="card">
            <h2>当前目标</h2>
            <p>预留管理后台路由、导航、表格和表单工作区位置。</p>
          </article>
          <article class="card">
            <h2>后续接入</h2>
            <p>权限矩阵、管理 API、二次确认机制和审计展示。</p>
          </article>
        </div>
      </section>
    </section>
  </main>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  background: #eef3f8;
  color: #122033;
}

.layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 240px 1fr;
}

.sidebar {
  background: #132033;
  color: #f7fbff;
  padding: 24px 18px;
}

.brand {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 600;
}

.nav {
  display: grid;
  gap: 8px;
}

.nav a {
  color: #b9c7da;
  text-decoration: none;
  padding: 8px 10px;
  border-radius: 6px;
}

.nav a:hover {
  background: #1d2f48;
  color: #fff;
}

.content {
  padding: 28px;
}

.content__header {
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
  font-size: 30px;
}

.badge {
  border: 1px solid #c7d4e5;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  background: #fff;
}

.cards {
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
</style>
