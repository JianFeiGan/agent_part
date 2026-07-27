<template>
  <div class="task-create">
    <el-card>
      <template #header>
        <span>创建任务</span>
      </template>

      <el-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        label-width="120px"
        style="max-width: 800px;"
      >
        <el-form-item label="关联商品" prop="product_id">
          <el-select
            v-model="formData.product_id"
            filterable
            placeholder="请选择关联商品"
            style="width: 100%;"
          >
            <el-option
              v-for="product in productList"
              :key="product.product_id"
              :label="product.name"
              :value="product.product_id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="任务类型" prop="task_type">
          <el-radio-group v-model="formData.task_type">
            <el-radio value="image_only">图片生成</el-radio>
            <el-radio value="video_only">视频生成</el-radio>
            <el-radio value="image_and_video">图片+视频</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 图片生成配置 -->
        <template v-if="formData.task_type === 'image_only' || formData.task_type === 'image_and_video'">
          <el-divider>图片生成配置</el-divider>

          <el-form-item label="图片类型">
            <el-checkbox-group v-model="formData.image_types">
              <el-checkbox label="main">主图</el-checkbox>
              <el-checkbox label="scene">场景图</el-checkbox>
              <el-checkbox label="selling_point">卖点图</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="每种类型数量">
            <el-input-number v-model="formData.image_count_per_type" :min="1" :max="10" />
          </el-form-item>
        </template>

        <!-- 视频生成配置 -->
        <template v-if="formData.task_type === 'video_only' || formData.task_type === 'image_and_video'">
          <el-divider>视频生成配置</el-divider>

          <el-form-item label="视频时长(秒)">
            <el-input-number v-model="formData.video_duration" :min="5" :max="300" :step="5" />
          </el-form-item>

          <el-form-item label="视频风格">
            <el-select v-model="formData.video_style" placeholder="请选择风格">
              <el-option label="专业商业" value="professional" />
              <el-option label="生活方式" value="lifestyle" />
              <el-option label="创意动画" value="creative" />
              <el-option label="简约优雅" value="elegant" />
            </el-select>
          </el-form-item>
        </template>

        <!-- 风格配置 -->
        <el-divider>风格配置</el-divider>

        <el-form-item label="风格偏好">
          <el-input v-model="formData.style_preference" placeholder="如：简约现代、科技感" />
        </el-form-item>

        <el-form-item label="颜色偏好">
          <el-input v-model="formData.color_preference" placeholder="如：蓝色系、暖色调" />
        </el-form-item>

        <el-form-item label="质量等级">
          <el-select v-model="formData.quality_level">
            <el-option label="标准" value="standard" />
            <el-option label="高质量" value="high" />
            <el-option label="超高质量" value="premium" />
          </el-select>
        </el-form-item>

        <!-- 模型厂商指定 -->
        <el-divider>模型厂商（可选）</el-divider>

        <el-form-item label="LLM 厂商">
          <el-select
            v-model="formData.llm_provider_id"
            placeholder="使用默认厂商"
            clearable
            style="width: 100%;"
          >
            <el-option
              v-for="p in llmProviders"
              :key="p.id"
              :label="`${p.display_name} (${p.default_model})`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="图片厂商" v-if="formData.task_type === 'image_only' || formData.task_type === 'image_and_video'">
          <el-select
            v-model="formData.image_provider_id"
            placeholder="使用默认厂商"
            clearable
            style="width: 100%;"
          >
            <el-option
              v-for="p in imageProviders"
              :key="p.id"
              :label="`${p.display_name} (${p.default_model})`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="视频厂商" v-if="formData.task_type === 'video_only' || formData.task_type === 'image_and_video'">
          <el-select
            v-model="formData.video_provider_id"
            placeholder="使用默认厂商"
            clearable
            style="width: 100%;"
          >
            <el-option
              v-for="p in videoProviders"
              :key="p.id"
              :label="`${p.display_name} (${p.default_model})`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            创建任务
          </el-button>
          <el-button @click="handleCancel">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import type { Product } from '@/types/product'
import type { TaskCreateRequest } from '@/types/task'
import type { ModelProviderResponse } from '@/types/provider'
import { getProducts } from '@/api/products'
import { createTask } from '@/api/tasks'
import { listModelProviders } from '@/api/providers'

/**
 * 创建任务页面
 */

const router = useRouter()
const route = useRoute()

// 表单引用
const formRef = ref<FormInstance>()

// 提交状态
const submitting = ref(false)

// 商品列表
const productList = ref<Product[]>([])

// 厂商列表
const llmProviders = ref<ModelProviderResponse[]>([])
const imageProviders = ref<ModelProviderResponse[]>([])
const videoProviders = ref<ModelProviderResponse[]>([])

// 表单数据
const formData = reactive<TaskCreateRequest>({
  product_id: '',
  task_type: 'image_and_video',
  image_types: ['main', 'scene', 'selling_point'],
  image_count_per_type: 1,
  video_duration: 30.0,
  video_style: 'professional',
  style_preference: '',
  color_preference: '',
  quality_level: 'standard',
  llm_provider_id: null,
  image_provider_id: null,
  video_provider_id: null
})

// 表单验证规则
const rules: FormRules = {
  product_id: [
    { required: true, message: '请选择关联商品', trigger: 'change' }
  ],
  task_type: [
    { required: true, message: '请选择任务类型', trigger: 'change' }
  ]
}

// 加载商品列表
const loadProducts = async () => {
  try {
    const response = await getProducts({ page: 1, page_size: 100 })
    if (response.data.code === 200) {
      productList.value = response.data.data.items

      // 如果有预设的商品 ID
      const preselectedProductId = route.query.product_id
      if (preselectedProductId) {
        formData.product_id = preselectedProductId as string
      }
    } else {
      ElMessage.error(response.data.message || '加载商品列表失败')
    }
  } catch (error) {
    console.error('加载商品列表失败:', error)
    ElMessage.error('加载商品列表失败')
  }
}

// 加载模型厂商列表
const loadProviders = async () => {
  try {
    const [llmRes, imageRes, videoRes] = await Promise.all([
      listModelProviders('llm'),
      listModelProviders('image'),
      listModelProviders('video'),
    ])
    if (llmRes.data.data) llmProviders.value = llmRes.data.data
    if (imageRes.data.data) imageProviders.value = imageRes.data.data
    if (videoRes.data.data) videoProviders.value = videoRes.data.data
  } catch {
    // 厂商列表加载失败不影响创建任务
    console.warn('加载模型厂商列表失败，将使用默认厂商')
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    submitting.value = true

    const response = await createTask(formData)
    if (response.data.code === 200 || response.data.code === 201) {
      ElMessage.success('任务创建成功')
      router.push('/tasks')
    } else {
      ElMessage.error(response.data.message || '创建任务失败')
    }
  } catch {
    // 验证失败
  } finally {
    submitting.value = false
  }
}

// 取消
const handleCancel = () => {
  router.back()
}

onMounted(() => {
  loadProducts()
  loadProviders()
})
</script>

<style scoped>
.task-create {
  padding: 0;
}
</style>