<script setup>
import { computed, ref } from "vue";
import { Icon } from "@iconify/vue";

const props = defineProps({ user: { type: Object, required: true } });
const emit = defineEmits(["logout"]);
const activeView = ref("概览");
const views = [
  { label: "概览", icon: "solar:widget-5-linear" },
  { label: "信号流", icon: "solar:radar-2-linear" },
  { label: "收藏", icon: "solar:bookmark-linear" },
];
const initial = computed(() => (props.user.display_name || props.user.email).slice(0, 1).toUpperCase());
const greetingName = computed(() => props.user.display_name || props.user.email.split("@")[0]);
</script>

<template>
  <section class="signal-console" aria-label="AI Signal 控制台">
    <aside class="console-sidebar">
      <div class="console-brand"><Icon icon="solar:orbit-bold" /><span>AI SIGNAL</span></div>
      <nav aria-label="控制台导航">
        <button v-for="view in views" :key="view.label" :class="{ active: activeView === view.label }" @click="activeView = view.label">
          <Icon :icon="view.icon" /><span>{{ view.label }}</span>
        </button>
      </nav>
      <div class="console-sidebar-footer"><span class="connection-dot" />采集器待连接</div>
    </aside>

    <main class="console-main">
      <header class="console-header">
        <div><p class="console-kicker">EVENT HORIZON / {{ activeView.toUpperCase() }}</p><h1>早上好，{{ greetingName }}</h1></div>
        <div class="console-actions"><button class="icon-button" type="button" aria-label="通知"><Icon icon="solar:bell-linear" /></button><button class="user-menu" type="button" @click="emit('logout')"><span>{{ initial }}</span><i>退出</i></button></div>
      </header>

      <section class="signal-hero">
        <div><p class="console-kicker">SIGNAL STATUS</p><h2>今天的 AI 信号正在校准</h2><p>内容采集器尚未接入。完成来源配置后，最新 AI 变化会在这里按优先级抵达。</p></div>
        <div class="collector-status" aria-label="采集器状态：等待首个来源">
          <div class="signal-core" aria-hidden="true"><span /><i /></div>
          <div><p>COLLECTOR STATUS</p><strong>等待首个来源</strong><span>0 个来源已连接</span></div>
        </div>
      </section>

      <section class="metric-grid" aria-label="信号概览">
        <article><Icon icon="solar:radar-2-linear" /><p>待处理信号</p><strong>0</strong><span>等待采集器接入</span></article>
        <article><Icon icon="solar:layers-minimalistic-linear" /><p>已接入来源</p><strong>0</strong><span>下一步配置首个来源</span></article>
        <article><Icon icon="solar:bookmark-linear" /><p>已收藏事件</p><strong>0</strong><span>在信号流中开始标记</span></article>
      </section>

      <section class="console-panel">
        <div class="panel-heading"><div><p class="console-kicker">LIVE FEED</p><h2>信号流</h2></div><button type="button" class="subtle-action" disabled>筛选器将在首个来源接入后启用</button></div>
        <div class="empty-feed"><Icon icon="solar:planet-3-linear" /><h3>事件视界仍在安静观测</h3><p>后端的认证通路已经建立。下一阶段接入资讯来源后，这里将显示统一、去重后的 AI 信息流。</p></div>
      </section>
    </main>
  </section>
</template>
