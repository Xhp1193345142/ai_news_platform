<script setup>
import { computed, onMounted, ref } from "vue";
import { Icon } from "@iconify/vue";
import ArticleChartTabs from "./ArticleChartTabs.vue";
import { fetchArticle, fetchArticles, fetchSources } from "../services/content";

const props = defineProps({ user: { type: Object, required: true } });
const emit = defineEmits(["logout"]);
const activeView = ref("概览");
const articles = ref([]);
const sources = ref([]);
const selectedArticle = ref(null);
const loading = ref(true);
const error = ref("");
const selectedCategory = ref("全部");
const selectedMediaTabs = ref({});
const categories = ["全部", "公司", "研究", "产品", "安全", "工程", "安全防护", "全球事务", "AI 采用", "应用 AI"];
const views = [
  { label: "概览", icon: "solar:widget-5-linear" },
  { label: "信号流", icon: "solar:radar-2-linear" },
  { label: "收藏", icon: "solar:bookmark-linear" },
];
const initial = computed(() => (props.user.display_name || props.user.email).slice(0, 1).toUpperCase());

async function loadContent() {
  loading.value = true;
  error.value = "";
  try {
    const [articlePage, sourceItems] = await Promise.all([fetchArticles(), fetchSources()]);
    articles.value = articlePage.items;
    sources.value = sourceItems;
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "资讯加载失败";
  } finally {
    loading.value = false;
  }
}

async function openArticle(article) {
  // Article detail belongs to the signal stream, regardless of whether it
  // was opened from the overview's latest-signal cards or from the feed.
  activeView.value = "信号流";
  selectedArticle.value = await fetchArticle(article.id);
}

async function selectCategory(category) {
  if (selectedCategory.value === category) return;
  selectedCategory.value = category;
  loading.value = true;
  error.value = "";
  try {
    articles.value = (await fetchArticles(category)).items;
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "分类加载失败";
  } finally {
    loading.value = false;
  }
}

function closeArticle() { selectedArticle.value = null; }
function goToFeed() { selectedArticle.value = null; activeView.value = "信号流"; }
function blockText(block) { return block.data?.text ?? ""; }
function activeMediaItem(block) {
  const selectedIndex = selectedMediaTabs.value[block.id] ?? 0;
  return block.data.items[selectedIndex] ?? block.data.items[0];
}
function selectMediaTab(block, index) {
  selectedMediaTabs.value = { ...selectedMediaTabs.value, [block.id]: index };
}

onMounted(loadContent);
</script>

<template>
  <section class="signal-console" aria-label="AI Signal 控制台">
    <header class="console-topbar">
      <div class="console-brand"><Icon icon="solar:orbit-bold" /><span>AI SIGNAL</span></div>
      <nav aria-label="控制台导航">
        <button v-for="view in views" :key="view.label" :class="{ active: activeView === view.label }" @click="activeView = view.label; selectedArticle = null"><Icon :icon="view.icon" /><span>{{ view.label }}</span></button>
      </nav>
      <div class="console-actions"><button class="icon-button" type="button" aria-label="刷新资讯" @click="loadContent"><Icon icon="solar:refresh-linear" /></button><button class="user-menu" type="button" @click="emit('logout')"><span>{{ initial }}</span><i>退出</i></button></div>
    </header>

    <main class="console-main">
      <p v-if="error" class="content-error" role="alert">{{ error }}</p>

      <article v-if="selectedArticle" class="article-reader console-panel">
        <button class="reader-back" type="button" @click="closeArticle"><Icon icon="solar:arrow-left-linear" />返回信号流</button>
        <header class="reader-header"><div class="reader-meta"><time>{{ new Date(selectedArticle.published_at).toLocaleDateString('zh-CN') }}</time><div class="article-topics"><span v-for="topic in selectedArticle.topics" :key="topic">{{ topic }}</span></div></div><h1>{{ selectedArticle.title }}</h1><p v-if="selectedArticle.subtitle" class="reader-subtitle">{{ selectedArticle.subtitle }}</p><span class="reader-author">{{ selectedArticle.author_name }}</span></header>
        <div class="reader-body">
          <template v-for="block in selectedArticle.content_blocks" :key="block.id">
            <p v-if="block.type === 'paragraph'" class="reader-paragraph">{{ blockText(block) }}</p>
            <component :is="`h${Math.min(Math.max(block.data.level ?? 2, 2), 4)}`" v-else-if="block.type === 'heading'" class="reader-source-heading">{{ block.data.text }}</component>
            <ol v-else-if="block.type === 'list' && block.data.ordered" class="reader-source-list"><li v-for="item in block.data.items" :key="item">{{ item }}</li></ol>
            <ul v-else-if="block.type === 'list'" class="reader-source-list"><li v-for="item in block.data.items" :key="item">{{ item }}</li></ul>
            <figure v-else-if="block.type === 'image'" class="reader-media"><img :src="block.data.url" :alt="block.data.alt" loading="lazy" /><figcaption v-if="block.data.alt">{{ block.data.alt }}</figcaption></figure>
            <figure v-else-if="block.type === 'video_embed'" class="reader-media reader-video"><div><iframe :src="block.data.embed_url" :title="block.data.alt || 'OpenAI 视频'" loading="lazy" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen /></div><figcaption v-if="block.data.alt">{{ block.data.alt }}</figcaption></figure>
            <section v-else-if="block.type === 'media_tabs'" class="reader-media-tabs">
              <div class="media-tab-list" role="tablist" aria-label="交互演示">
                <button v-for="(item, index) in block.data.items" :id="`${block.id}-tab-${index}`" :key="item.embed_url" type="button" role="tab" :aria-selected="(selectedMediaTabs[block.id] ?? 0) === index" :aria-controls="`${block.id}-panel`" :class="{ active: (selectedMediaTabs[block.id] ?? 0) === index }" @click="selectMediaTab(block, index)">{{ item.label }}</button>
              </div>
              <figure :id="`${block.id}-panel`" class="reader-media reader-video media-tab-panel" role="tabpanel" :aria-labelledby="`${block.id}-tab-${selectedMediaTabs[block.id] ?? 0}`">
                <div><iframe :key="activeMediaItem(block).embed_url" :src="activeMediaItem(block).embed_url" :title="activeMediaItem(block).alt" loading="lazy" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen /></div>
                <figcaption v-if="activeMediaItem(block).alt">{{ activeMediaItem(block).alt }}</figcaption>
              </figure>
            </section>
            <ArticleChartTabs v-else-if="block.type === 'chart_tabs'" :block="block" />
            <div v-else-if="block.type === 'table'" class="reader-table-wrap"><table class="reader-table"><thead><tr><th v-for="header in block.data.headers" :key="header" scope="col">{{ header }}</th></tr></thead><tbody><tr v-for="(row, rowIndex) in block.data.rows" :key="rowIndex"><th scope="row">{{ row[0] }}</th><td v-for="(cell, cellIndex) in row.slice(1)" :key="cellIndex">{{ cell }}</td></tr></tbody></table></div>
            <div v-else-if="block.type === 'table_row'" class="reader-table-row"><span v-for="cell in block.data.cells" :key="cell">{{ cell }}</span></div>
            <section v-else-if="block.type === 'section'" class="reader-section"><h2>{{ block.data.title }}</h2><p v-for="paragraph in block.data.paragraphs" :key="paragraph">{{ paragraph }}</p></section>
            <ul v-else-if="block.type === 'key_points'" class="reader-key-points"><li v-for="item in block.data.items" :key="item">{{ item }}</li></ul>
            <blockquote v-else-if="block.type === 'quote'"><p>{{ block.data.text }}</p><cite>{{ block.data.attribution }}</cite></blockquote>
            <figure v-else-if="block.type === 'chart'" class="reader-chart"><figcaption>{{ block.data.title }}</figcaption><div v-for="item in block.data.series" :key="item.name" class="chart-row"><span>{{ item.name }}</span><i :style="{ width: `${item.value * 28}%` }" /><b>{{ item.label }}</b></div><small>{{ block.data.note }}</small></figure>
            <a v-else-if="block.type === 'source_link'" class="source-link" :href="block.data.url" target="_blank" rel="noreferrer">{{ block.data.label }}<Icon icon="solar:arrow-right-up-linear" /></a>
          </template>
        </div>
      </article>

      <template v-else-if="activeView === '概览'">
        <section class="signal-hero"><div><p class="console-kicker">SIGNAL STATUS</p><h2>{{ articles.length ? 'OpenAI 信号已进入事件视界' : '今天的 AI 信号正在校准' }}</h2><p>{{ articles.length ? '首批真实文章已完成规范化、去重和分块存储。' : '完成来源配置后，最新 AI 变化会在这里抵达。' }}</p></div><div class="collector-status"><div class="signal-core" aria-hidden="true"><span /><i /></div><div><p>COLLECTOR STATUS</p><strong>{{ sources.length ? 'OpenAI 已连接' : '等待首个来源' }}</strong><span>{{ sources.length }} 个来源已连接</span></div></div></section>
        <section class="metric-grid" aria-label="信号概览"><article><Icon icon="solar:radar-2-linear" /><p>可浏览信号</p><strong>{{ articles.length }}</strong><span>已规范化并入库</span></article><article><Icon icon="solar:layers-minimalistic-linear" /><p>已接入来源</p><strong>{{ sources.length }}</strong><span>{{ sources[0]?.name ?? '等待接入' }}</span></article><article><Icon icon="solar:bookmark-linear" /><p>已收藏事件</p><strong>0</strong><span>收藏能力将在下一阶段接入</span></article></section>
        <section class="console-panel"><div class="panel-heading"><div><p class="console-kicker">LIVE FEED</p><h2>最新信号</h2></div><button class="subtle-action" type="button" @click="goToFeed">查看全部</button></div><div v-if="loading" class="empty-feed"><p>正在校准信号…</p></div><div v-else class="article-preview-list"><button v-for="article in articles.slice(0, 2)" :key="article.id" @click="openArticle(article)"><span>{{ article.topics.join(' · ') }}</span><strong>{{ article.title }}</strong><p>{{ article.summary }}</p></button></div></section>
      </template>

      <section v-else-if="activeView === '信号流'" class="event-explorer" aria-label="AI 事件浏览">
        <header class="event-explorer-header"><div><p class="console-kicker">AI NEWS INTELLIGENCE</p><h1>信号流</h1><p>来源真实、结构统一、原文可追溯。</p></div><div class="event-count"><strong>{{ articles.length }}</strong><span>个可浏览事件</span></div></header>
        <nav class="event-toolbar" aria-label="文章分类筛选"><div class="filter-group"><button v-for="category in categories" :key="category" type="button" class="filter-chip" :class="{ active: selectedCategory === category }" :aria-pressed="selectedCategory === category" @click="selectCategory(category)">{{ category }}</button></div></nav>
        <section class="event-list console-panel"><div v-if="!articles.length && !loading" class="empty-feed"><h3>该分类暂无文章</h3><p>切换到“全部”查看已采集内容。</p></div><div class="signal-article-grid"><button v-for="article in articles" :key="article.id" class="signal-article-card" @click="openArticle(article)"><div class="article-topics"><span v-for="topic in article.topics" :key="topic">{{ topic }}</span></div><h2>{{ article.title }}</h2><p v-if="article.summary">{{ article.summary }}</p><footer><span>{{ article.author_name }}</span><time>{{ new Date(article.published_at).toLocaleDateString('zh-CN') }}</time></footer></button></div></section>
      </section>

      <section v-else class="event-explorer saved-events"><div class="empty-feed console-panel"><Icon icon="solar:bookmark-linear" /><h3>尚未收藏事件</h3><p>收藏数据模型将在下一阶段接入。</p><button class="subtle-action" type="button" @click="goToFeed">前往信号流</button></div></section>
    </main>
  </section>
</template>
