<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh;">
    <el-card style="width: 400px;">
      <h2>登录</h2>
      <el-form @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input v-model="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" />
        </el-form-item>
        <el-button type="primary" @click="handleLogin" style="width: 100%;">登录</el-button>
        <el-button text @click="$router.push('/register')" style="width: 100%; margin-top: 10px;">注册账号</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'
import api from '../api/client'

const username = ref('')
const password = ref('')
const router = useRouter()
const userStore = useUserStore()

async function handleLogin() {
  try {
    const { data } = await api.post('/api/auth/login', { username: username.value, password: password.value })
    userStore.setToken(data.token)
    userStore.setUser(data.user)
    router.push('/novels')
  } catch (error) {
    ElMessage.error('登录失败')
  }
}
</script>
