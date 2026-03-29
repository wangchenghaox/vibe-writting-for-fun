<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh;">
    <el-card style="width: 400px;">
      <h2>注册</h2>
      <el-form @submit.prevent="handleRegister">
        <el-form-item label="用户名">
          <el-input v-model="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" />
        </el-form-item>
        <el-button type="primary" @click="handleRegister" style="width: 100%;">注册</el-button>
        <el-button text @click="$router.push('/login')" style="width: 100%; margin-top: 10px;">已有账号？登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/client'

const username = ref('')
const password = ref('')
const router = useRouter()

async function handleRegister() {
  try {
    await api.post('/api/auth/register', { username: username.value, password: password.value })
    ElMessage.success('注册成功')
    router.push('/login')
  } catch (error) {
    ElMessage.error('注册失败')
  }
}
</script>
