<script setup>
import { computed, onMounted, ref } from "vue";
import { Icon } from "@iconify/vue";
import BlackHoleCanvas from "./components/BlackHoleCanvas.vue";
import SignalConsole from "./components/SignalConsole.vue";
import { authenticate, clearSession, fetchCurrentUser, getStoredSession, refreshSession, revokeSession } from "./services/auth";

const mode = ref("login");
const showPassword = ref(false);
const isTransitioning = ref(false);
const isConsoleVisible = ref(false);
const isCentering = ref(false);
const currentUser = ref(null);
const isSubmitting = ref(false);
const email = ref("");
const password = ref("");
const confirmPassword = ref("");
const feedback = ref("");
const blackHoleCanvas = ref(null);
const isLogin = computed(() => mode.value === "login");
const hasEntered = computed(() => Boolean(currentUser.value) && isConsoleVisible.value);
const heading = computed(() => (isLogin.value ? "欢迎回来" : "创建你的观测站"));
const helper = computed(() => isLogin.value ? "进入事件视界，看见 AI 的下一步" : "定制主题，追踪你关心的 AI 信号");
const submitLabel = computed(() => (isLogin.value ? "进入事件视界" : "创建账户"));

function changeMode(nextMode) { mode.value = nextMode; feedback.value = ""; confirmPassword.value = ""; }
async function submit() {
  if (!email.value || !password.value || (!isLogin.value && password.value !== confirmPassword.value)) {
    feedback.value = !isLogin.value && password.value !== confirmPassword.value ? "两次输入的密码不一致" : "请填写完整的账户信息";
    return;
  }
  feedback.value = "";
  isSubmitting.value = true;
  try {
    const session = await authenticate(isLogin.value ? "login" : "register", { email: email.value, password: password.value });
    blackHoleCanvas.value?.triggerGlitch();
    isTransitioning.value = true;
    // Let the glitch build first, then hide the lens shift within its peak.
    window.setTimeout(() => { isCentering.value = true; }, 150);
    window.setTimeout(() => {
      currentUser.value = session.user;
      isConsoleVisible.value = true;
      isTransitioning.value = false;
    }, 1000);
  } catch (error) {
    feedback.value = error instanceof Error ? error.message : "认证失败，请稍后重试";
  } finally {
    isSubmitting.value = false;
  }
}
function continueWith(provider) { feedback.value = `正在连接 ${provider}…`; }
async function logout() {
  const session = getStoredSession();
  try { await revokeSession(session?.refresh_token); } catch { clearSession(); }
  currentUser.value = null;
  isConsoleVisible.value = false;
  isCentering.value = false;
  isTransitioning.value = false;
  password.value = "";
  feedback.value = "";
}
onMounted(async () => {
  const session = getStoredSession();
  if (!session?.access_token) return;
  try {
    currentUser.value = await fetchCurrentUser(session.access_token);
    isConsoleVisible.value = true;
  } catch {
    try {
      const refreshedSession = await refreshSession(session.refresh_token);
      currentUser.value = refreshedSession.user;
      isConsoleVisible.value = true;
    } catch {
      clearSession();
    }
  }
});
</script>

<template>
  <main class="auth-experience" :class="{ 'is-transitioning': isTransitioning, 'has-entered': hasEntered }">
    <div class="black-hole-system"><BlackHoleCanvas ref="blackHoleCanvas" :scene-mode="isCentering || hasEntered ? 'console' : 'auth'" /></div>
    <div class="space-veil" aria-hidden="true" />
    <section class="scene-copy" aria-label="产品介绍">
      <p class="eyebrow"><span /> AI NEWS INTELLIGENCE</p>
      <h1>进入事件视界，<br />看见 AI 的下一步</h1>
      <p>收集信号、消除噪声，并让关键变化首先抵达你。</p>
    </section>
    <section v-if="!hasEntered" class="auth-panel" aria-label="账户认证">
      <div class="panel-edge panel-edge--warm" aria-hidden="true" />
      <div class="panel-edge panel-edge--cool" aria-hidden="true" />
      <header class="brand-lockup"><span class="brand-mark"><Icon icon="solar:orbit-bold" /></span><span>AI SIGNAL</span></header>
      <div class="panel-intro"><p class="panel-kicker">{{ isLogin ? "WELCOME BACK" : "START OBSERVING" }}</p><h2>{{ heading }}</h2><p>{{ helper }}</p></div>
      <form class="auth-form" @submit.prevent="submit">
        <label class="field"><span>邮箱地址</span><div class="field-control"><Icon icon="solar:letter-linear" /><input v-model.trim="email" type="email" autocomplete="email" placeholder="name@example.com" /></div></label>
        <label class="field"><span>{{ isLogin ? "密码" : "设置密码" }}</span><div class="field-control"><Icon icon="solar:lock-keyhole-linear" /><input v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="至少 8 位字符" /><button class="visibility-toggle" type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword"><Icon :icon="showPassword ? 'solar:eye-linear' : 'solar:eye-closed-linear'" /></button></div></label>
        <label v-if="!isLogin" class="field"><span>确认密码</span><div class="field-control"><Icon icon="solar:shield-check-linear" /><input v-model="confirmPassword" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" placeholder="再次输入密码" /></div></label>
        <div class="form-meta"><label v-if="isLogin" class="remember"><input type="checkbox" /><span>保持登录</span></label><button v-if="isLogin" class="text-action" type="button">忘记密码？</button></div>
        <p v-if="feedback" class="feedback" role="status">{{ feedback }}</p>
        <button class="primary-action" type="submit" :disabled="isSubmitting"><span>{{ isSubmitting ? "正在验证…" : submitLabel }}</span><Icon icon="solar:arrow-right-up-linear" /></button>
      </form>
      <div class="divider"><span /> 或 <span /></div>
      <div class="social-actions"><button type="button" @click="continueWith('GitHub')"><Icon icon="mdi:github" />继续使用 GitHub {{ isLogin ? "登录" : "注册" }}</button><button type="button" @click="continueWith('Google')"><Icon icon="logos:google-icon" />继续使用 Google {{ isLogin ? "登录" : "注册" }}</button></div>
      <p class="mode-switch">{{ isLogin ? "还没有账号？" : "已有账户？" }}<button type="button" @click="changeMode(isLogin ? 'register' : 'login')">{{ isLogin ? "注册" : "登录" }}</button></p>
    </section>
    <Transition name="console-reveal"><SignalConsole v-if="hasEntered" :user="currentUser" @logout="logout" /></Transition>
  </main>
</template>
