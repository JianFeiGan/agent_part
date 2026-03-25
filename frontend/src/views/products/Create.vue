<template>
  <div class="product-create">
    <el-card>
      <template #header>
        <span>创建商品</span>
      </template>

      <el-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        label-width="120px"
        style="max-width: 800px;"
      >
        <el-form-item label="商品名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入商品名称" maxlength="100" show-word-limit />
        </el-form-item>

        <el-form-item label="品牌" prop="brand">
          <el-input v-model="formData.brand" placeholder="请输入品牌名称" maxlength="50" />
        </el-form-item>

        <el-form-item label="商品类目" prop="category">
          <el-select v-model="formData.category" placeholder="请选择类目">
            <el-option
              v-for="(label, value) in ProductCategoryLabels"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="子类目" prop="subcategory">
          <el-input v-model="formData.subcategory" placeholder="请输入子类目" maxlength="50" />
        </el-form-item>

        <el-form-item label="商品描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="4"
            placeholder="请输入商品描述"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="短描述" prop="short_description">
          <el-input
            v-model="formData.short_description"
            placeholder="用于图片文案，不超过100字"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="目标人群" prop="target_audience">
          <el-select
            v-model="formData.target_audience"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="请输入或选择目标人群"
          >
            <el-option label="运动爱好者" value="运动爱好者" />
            <el-option label="上班族" value="上班族" />
            <el-option label="学生" value="学生" />
            <el-option label="中老年人" value="中老年人" />
          </el-select>
        </el-form-item>

        <el-form-item label="标签" prop="tags">
          <el-select
            v-model="formData.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="请输入或选择标签"
          >
            <el-option label="新品" value="新品" />
            <el-option label="热销" value="热销" />
            <el-option label="促销" value="促销" />
            <el-option label="限量" value="限量" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            创建商品
          </el-button>
          <el-button @click="handleCancel">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { ProductCategoryLabels, ProductCategory } from '@/types/product'
import type { ProductCreateRequest } from '@/types/product'
import { createProduct } from '@/api/products'

/**
 * 创建商品页面
 */

const router = useRouter()

// 表单引用
const formRef = ref<FormInstance>()

// 提交状态
const submitting = ref(false)

// 表单数据
const formData = reactive<ProductCreateRequest>({
  name: '',
  brand: '',
  category: ProductCategory.DIGITAL,
  subcategory: '',
  description: '',
  short_description: '',
  target_audience: [],
  tags: [],
  selling_points: [],
  specifications: [],
  existing_images: [],
  existing_videos: []
})

// 表单验证规则
const rules: FormRules = {
  name: [
    { required: true, message: '请输入商品名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' }
  ],
  category: [
    { required: true, message: '请选择商品类目', trigger: 'change' }
  ],
  description: [
    { required: true, message: '请输入商品描述', trigger: 'blur' },
    { min: 10, max: 2000, message: '长度在 10 到 2000 个字符', trigger: 'blur' }
  ]
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    submitting.value = true

    const response = await createProduct(formData)
    if (response.data.code === 200 || response.data.code === 201) {
      ElMessage.success('商品创建成功')
      router.push('/products')
    } else {
      ElMessage.error(response.data.message || '创建商品失败')
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
</script>

<style scoped>
.product-create {
  padding: 0;
}
</style>