<template>
	<view class="uni-file-picker">
		<view v-if="title" class="uni-file-picker__header">
			<text class="file-title">{{ title }}</text>
			<text class="file-count">{{ filesList.length }}/{{ limitLength }}</text>
		</view>
		<upload-image v-if="fileMediatype === 'image' && showType === 'grid'" :readonly="readonly"
			:image-styles="imageStyles" :files-list="filesList" :limit="limitLength" :disablePreview="disablePreview"
			:delIcon="delIcon" @uploadFiles="uploadFiles" @choose="choose" @delFile="delFile">
			<slot>
				<view class="is-add">
					<view class="icon-add"></view>
					<view class="icon-add rotate"></view>
				</view>
			</slot>
		</upload-image>
		<upload-file v-if="fileMediatype !== 'image' || showType !== 'grid'" :readonly="readonly"
			:list-styles="listStyles" :files-list="filesList" :showType="showType" :delIcon="delIcon"
			@uploadFiles="uploadFiles" @choose="choose" @delFile="delFile">
			<slot><button type="primary" size="mini">閫夋嫨鏂囦欢</button></slot>
		</upload-file>
	</view>
</template>

<script>
	import {
		chooseAndUploadFile,
		uploadCloudFiles
	} from './choose-and-upload-file.js'
	import {
		get_file_ext,
		get_extname,
		get_files_and_is_max,
		get_file_info,
		get_file_data
	} from './utils.js'
	import uploadImage from './upload-image.vue'
	import uploadFile from './upload-file.vue'
	let fileInput = null
	/**
	 * FilePicker 鏂囦欢閫夋嫨涓婁紶
	 * @description 鏂囦欢閫夋嫨涓婁紶缁勪欢锛屽彲浠ラ€夋嫨鍥剧墖銆佽棰戠瓑浠绘剰鏂囦欢骞朵笂浼犲埌褰撳墠缁戝畾鐨勬湇鍔＄┖闂?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=4079
	 * @property {Object|Array}	value	缁勪欢鏁版嵁锛岄€氬父鐢ㄦ潵鍥炴樉 ,绫诲瀷鐢眗eturn-type灞炴€у喅瀹?
	 * @property {Boolean}	disabled = [true|false]	缁勪欢绂佺敤
	 * 	@value true 	绂佺敤
	 * 	@value false 	鍙栨秷绂佺敤
	 * @property {Boolean}	readonly = [true|false]	缁勪欢鍙锛屼笉鍙€夋嫨锛屼笉鏄剧ず杩涘害锛屼笉鏄剧ず鍒犻櫎鎸夐挳
	 * 	@value true 	鍙
	 * 	@value false 	鍙栨秷鍙
	 * @property {String}	return-type = [array|object]	闄愬埗 value 鏍煎紡锛屽綋涓?object 鏃?锛岀粍浠跺彧鑳藉崟閫夛紝涓斾細瑕嗙洊
	 * 	@value array	瑙勫畾 value 灞炴€х殑绫诲瀷涓烘暟缁?
	 * 	@value object	瑙勫畾 value 灞炴€х殑绫诲瀷涓哄璞?
	 * @property {Boolean}	disable-preview = [true|false]	绂佺敤鍥剧墖棰勮锛屼粎 mode:grid 鏃剁敓鏁?
	 * 	@value true 	绂佺敤鍥剧墖棰勮
	 * 	@value false 	鍙栨秷绂佺敤鍥剧墖棰勮
	 * @property {Boolean}	del-icon = [true|false]	鏄惁鏄剧ず鍒犻櫎鎸夐挳
	 * 	@value true 	鏄剧ず鍒犻櫎鎸夐挳
	 * 	@value false 	涓嶆樉绀哄垹闄ゆ寜閽?
	 * @property {Boolean}	auto-upload = [true|false]	鏄惁鑷姩涓婁紶锛屽€间负true鍒欏彧瑙﹀彂@select,鍙嚜琛屼笂浼?
	 * 	@value true 	鑷姩涓婁紶
	 * 	@value false 	鍙栨秷鑷姩涓婁紶
	 * @property {Number|String}	limit	鏈€澶ч€夋嫨涓暟 锛宧5 浼氳嚜鍔ㄥ拷鐣ュ閫夌殑閮ㄥ垎
	 * @property {String}	title	缁勪欢鏍囬锛屽彸渚ф樉绀轰笂浼犺鏁?
	 * @property {String}	mode = [list|grid]	閫夋嫨鏂囦欢鍚庣殑鏂囦欢鍒楄〃鏍峰紡
	 * 	@value list 	鍒楄〃鏄剧ず
	 * 	@value grid 	瀹牸鏄剧ず
	 * @property {String}	file-mediatype = [image|video|all]	閫夋嫨鏂囦欢绫诲瀷
	 * 	@value image	鍙€夋嫨鍥剧墖
	 * 	@value video	鍙€夋嫨瑙嗛
	 * 	@value all		閫夋嫨鎵€鏈夋枃浠?
	 * @property {Array}	file-extname	閫夋嫨鏂囦欢鍚庣紑锛屾牴鎹?file-mediatype 灞炴€ц€屼笉鍚?
	 * @property {Object}	list-style	mode:list 鏃剁殑鏍峰紡
	 * @property {Object}	image-styles	閫夋嫨鏂囦欢鍚庣紑锛屾牴鎹?file-mediatype 灞炴€ц€屼笉鍚?
	 * @event {Function} select 	閫夋嫨鏂囦欢鍚庤Е鍙?
	 * @event {Function} progress 鏂囦欢涓婁紶鏃惰Е鍙?
	 * @event {Function} success 	涓婁紶鎴愬姛瑙﹀彂
	 * @event {Function} fail 		涓婁紶澶辫触瑙﹀彂
	 * @event {Function} delete 	鏂囦欢浠庡垪琛ㄧЩ闄ゆ椂瑙﹀彂
	 */
	export default {
		name: 'uniFilePicker',
		components: {
			uploadImage,
			uploadFile
		},
		options: {
			virtualHost: true
		},
		emits: ['select', 'success', 'fail', 'progress', 'delete', 'update:modelValue', 'input'],
		props: {
			modelValue: {
				type: [Array, Object],
				default () {
					return []
				}
			},
			value: {
				type: [Array, Object],
				default () {
					return []
				}
			},
			disabled: {
				type: Boolean,
				default: false
			},
			disablePreview: {
				type: Boolean,
				default: false
			},
			delIcon: {
				type: Boolean,
				default: true
			},
			// 鑷姩涓婁紶
			autoUpload: {
				type: Boolean,
				default: true
			},
			// 鏈€澶ч€夋嫨涓暟 锛宧5鍙兘闄愬埗鍗曢€夋垨鏄閫?
			limit: {
				type: [Number, String],
				default: 9
			},
			// 鍒楄〃鏍峰紡 grid | list | list-card
			mode: {
				type: String,
				default: 'grid'
			},
			// 閫夋嫨鏂囦欢绫诲瀷  image/video/all
			fileMediatype: {
				type: String,
				default: 'image'
			},
			// 鏂囦欢绫诲瀷绛涢€?
			fileExtname: {
				type: [Array, String],
				default () {
					return []
				}
			},
			title: {
				type: String,
				default: ''
			},
			listStyles: {
				type: Object,
				default () {
					return {
						// 鏄惁鏄剧ず杈规
						border: true,
						// 鏄惁鏄剧ず鍒嗛殧绾?
						dividline: true,
						// 绾挎潯鏍峰紡
						borderStyle: {}
					}
				}
			},
			imageStyles: {
				type: Object,
				default () {
					return {
						width: 'auto',
						height: 'auto'
					}
				}
			},
			readonly: {
				type: Boolean,
				default: false
			},
			returnType: {
				type: String,
				default: 'array'
			},
			sizeType: {
				type: Array,
				default () {
					return ['original', 'compressed']
				}
			},
			sourceType: {
				type: Array,
				default () {
					return  ['album', 'camera']
				}
			},
			provider: {
				type: String,
				default: '' // 榛樿涓婁紶鍒?unicloud 鍐呯疆瀛樺偍 extStorage 鎵╁睍瀛樺偍
			}
		},
		data() {
			return {
				files: [],
				localValue: []
			}
		},
		watch: {
			value: {
				handler(newVal, oldVal) {
					this.setValue(newVal, oldVal)
				},
				immediate: true
			},
			modelValue: {
				handler(newVal, oldVal) {
					this.setValue(newVal, oldVal)
				},
				immediate: true
			},
		},
		computed: {
			filesList() {
				let files = []
				this.files.forEach(v => {
					files.push(v)
				})
				return files
			},
			showType() {
				if (this.fileMediatype === 'image') {
					return this.mode
				}
				return 'list'
			},
			limitLength() {
				if (this.returnType === 'object') {
					return 1
				}
				if (!this.limit) {
					return 1
				}
				if (this.limit >= 9) {
					return 9
				}
				return this.limit
			}
		},
		created() {
			// TODO 鍏煎涓嶅紑閫氭湇鍔＄┖闂寸殑鎯呭喌
			if (!(uniCloud.config && uniCloud.config.provider)) {
				this.noSpace = true
				uniCloud.chooseAndUploadFile = chooseAndUploadFile
			}
			this.form = this.getForm('uniForms')
			this.formItem = this.getForm('uniFormsItem')
			if (this.form && this.formItem) {
				if (this.formItem.name) {
					this.rename = this.formItem.name
					this.form.inputChildrens.push(this)
				}
			}
		},
		methods: {
			/**
			 * 鍏紑鐢ㄦ埛浣跨敤锛屾竻绌烘枃浠?
			 * @param {Object} index
			 */
			clearFiles(index) {
				if (index !== 0 && !index) {
					this.files = []
					this.$nextTick(() => {
						this.setEmit()
					})
				} else {
					this.files.splice(index, 1)
				}
				this.$nextTick(() => {
					this.setEmit()
				})
			},
			/**
			 * 鍏紑鐢ㄦ埛浣跨敤锛岀户缁笂浼?
			 */
			upload() {
				let files = []
				this.files.forEach((v, index) => {
					if (v.status === 'ready' || v.status === 'error') {
						files.push(Object.assign({}, v))
					}
				})
				return this.uploadFiles(files)
			},
			async setValue(newVal, oldVal) {
				const newData =  async (v) => {
					const reg = /cloud:\/\/([\w.]+\/?)\S*/
					let url = ''
					if(v.fileID){
						url = v.fileID
					}else{
						url = v.url
					}
					if (reg.test(url)) {
						v.fileID = url
						v.url = await this.getTempFileURL(url)
					}
					if(v.url) v.path = v.url
					return v
				}
				if (this.returnType === 'object') {
					if (newVal) {
						await newData(newVal)
					} else {
						newVal = {}
					}
				} else {
					if (!newVal) newVal = []
					for(let i =0 ;i < newVal.length ;i++){
						let v = newVal[i]
						await newData(v)
					}
				}
				this.localValue = newVal
				if (this.form && this.formItem &&!this.is_reset) {
					this.is_reset = false
					this.formItem.setValue(this.localValue)
				}
				let filesData = Object.keys(newVal).length > 0 ? newVal : [];
				this.files = [].concat(filesData)
			},

			/**
			 * 閫夋嫨鏂囦欢
			 */
			choose() {
				if (this.disabled) return
				if (this.files.length >= Number(this.limitLength) && this.showType !== 'grid' && this.returnType ===
					'array') {
					uni.showToast({
						title: `鎮ㄦ渶澶氶€夋嫨 ${this.limitLength} 涓枃浠禶,
						icon: 'none'
					})
					return
				}
				this.chooseFiles()
			},

			/**
			 * 閫夋嫨鏂囦欢骞朵笂浼?
			 */
			chooseFiles() {
				const _extname = get_extname(this.fileExtname)
				// 鑾峰彇鍚庣紑
				uniCloud
					.chooseAndUploadFile({
						type: this.fileMediatype,
						compressed: false,
						sizeType: this.sizeType,
						sourceType: this.sourceType,
						// TODO 濡傛灉涓虹┖锛寁ideo 鏈夐棶棰?
						extension: _extname.length > 0 ? _extname : undefined,
						count: this.limitLength - this.files.length, //榛樿9
						onChooseFile: this.chooseFileCallback,
						onUploadProgress: progressEvent => {
							this.setProgress(progressEvent, progressEvent.index)
						}
					})
					.then(result => {
						this.setSuccessAndError(result.tempFiles)
					})
					.catch(err => {
						console.log('閫夋嫨澶辫触', err)
					})
			},

			/**
			 * 閫夋嫨鏂囦欢鍥炶皟
			 * @param {Object} res
			 */
			async chooseFileCallback(res) {
				const _extname = get_extname(this.fileExtname)
				const is_one = (Number(this.limitLength) === 1 &&
						this.disablePreview &&
						!this.disabled) ||
					this.returnType === 'object'
				// 濡傛灉杩欐湁涓€涓枃浠?锛岄渶瑕佹竻绌烘湰鍦扮紦瀛樻暟鎹?
				if (is_one) {
					this.files = []
				}

				let {
					filePaths,
					files
				} = get_files_and_is_max(res, _extname)
				if (!(_extname && _extname.length > 0)) {
					filePaths = res.tempFilePaths
					files = res.tempFiles
				}

				let currentData = []
				for (let i = 0; i < files.length; i++) {
					if (this.limitLength - this.files.length <= 0) break
					files[i].uuid = Date.now()
					let filedata = await get_file_data(files[i], this.fileMediatype)
					filedata.progress = 0
					filedata.status = 'ready'
					this.files.push(filedata)
					currentData.push({
						...filedata,
						file: files[i]
					})
				}
				this.$emit('select', {
					tempFiles: currentData,
					tempFilePaths: filePaths
				})
				res.tempFiles = files
				// 鍋滄鑷姩涓婁紶
				if (!this.autoUpload || this.noSpace) {
					res.tempFiles = []
				}
				res.tempFiles.forEach((fileItem, index) => {
					this.provider && (fileItem.provider = this.provider);
					const fileNameSplit = fileItem.name.split('.')
					const ext = fileNameSplit.pop()
					const fileName = fileNameSplit.join('.').replace(/[\s\/\?<>\\:\*\|":]/g, '_')
					fileItem.cloudPath = fileName + '_' + Date.now() + '_' + index + '.' + ext
				})
			},

			/**
			 * 鎵逛紶
			 * @param {Object} e
			 */
			uploadFiles(files) {
				files = [].concat(files)
				return uploadCloudFiles.call(this, files, 5, res => {
						this.setProgress(res, res.index, true)
					})
					.then(result => {
						this.setSuccessAndError(result)
						return result;
					})
					.catch(err => {
						console.log(err)
					})
			},

			/**
			 * 鎴愬姛鎴栧け璐?
			 */
			async setSuccessAndError(res, fn) {
				let successData = []
				let errorData = []
				let tempFilePath = []
				let errorTempFilePath = []
				for (let i = 0; i < res.length; i++) {
					const item = res[i]
					const index = item.uuid ? this.files.findIndex(p => p.uuid === item.uuid) : item.index

					if (index === -1 || !this.files) break
					if (item.errMsg === 'request:fail') {
						this.files[index].url = item.path
						this.files[index].status = 'error'
						this.files[index].errMsg = item.errMsg
						// this.files[index].progress = -1
						errorData.push(this.files[index])
						errorTempFilePath.push(this.files[index].url)
					} else {
						this.files[index].errMsg = ''
						this.files[index].fileID = item.url
						const reg = /cloud:\/\/([\w.]+\/?)\S*/
						if (reg.test(item.url)) {
							this.files[index].url = await this.getTempFileURL(item.url)
						}else{
							this.files[index].url = item.url
						}

						this.files[index].status = 'success'
						this.files[index].progress += 1
						successData.push(this.files[index])
						tempFilePath.push(this.files[index].fileID)
					}
				}

				if (successData.length > 0) {
					this.setEmit()
					// 鐘舵€佹敼鍙樿繑鍥?
					this.$emit('success', {
						tempFiles: this.backObject(successData),
						tempFilePaths: tempFilePath
					})
				}

				if (errorData.length > 0) {
					this.$emit('fail', {
						tempFiles: this.backObject(errorData),
						tempFilePaths: errorTempFilePath
					})
				}
			},

			/**
			 * 鑾峰彇杩涘害
			 * @param {Object} progressEvent
			 * @param {Object} index
			 * @param {Object} type
			 */
			setProgress(progressEvent, index, type) {
				const fileLenth = this.files.length
				const percentNum = (index / fileLenth) * 100
				const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
				let idx = index
				if (!type) {
					idx = this.files.findIndex(p => p.uuid === progressEvent.tempFile.uuid)
				}
				if (idx === -1 || !this.files[idx]) return
				// fix by mehaotian 100 灏变細娑堝け锛?1 鏄负浜嗚杩涘害鏉℃秷澶?
				this.files[idx].progress = percentCompleted - 1
				// 涓婁紶涓?
				this.$emit('progress', {
					index: idx,
					progress: parseInt(percentCompleted),
					tempFile: this.files[idx]
				})
			},

			/**
			 * 鍒犻櫎鏂囦欢
			 * @param {Object} index
			 */
			delFile(index) {
				this.$emit('delete', {
					index,
					tempFile: this.files[index],
					tempFilePath: this.files[index].url
				})
				this.files.splice(index, 1)
				this.$nextTick(() => {
					this.setEmit()
				})
			},

			/**
			 * 鑾峰彇鏂囦欢鍚嶅拰鍚庣紑
			 * @param {Object} name
			 */
			getFileExt(name) {
				const last_len = name.lastIndexOf('.')
				const len = name.length
				return {
					name: name.substring(0, last_len),
					ext: name.substring(last_len + 1, len)
				}
			},

			/**
			 * 澶勭悊杩斿洖浜嬩欢
			 */
			setEmit() {
				let data = []
				if (this.returnType === 'object') {
					data = this.backObject(this.files)[0]
					this.localValue = data?data:null
				} else {
					data = this.backObject(this.files)
					if (!this.localValue) {
						this.localValue = []
					}
					this.localValue = [...data]
				}
				// #ifdef VUE3
				this.$emit('update:modelValue', this.localValue)
				// #endif
				// #ifndef VUE3
				this.$emit('input', this.localValue)
				// #endif
			},

			/**
			 * 澶勭悊杩斿洖鍙傛暟
			 * @param {Object} files
			 */
			backObject(files) {
				let newFilesData = []
				files.forEach(v => {
					newFilesData.push({
						extname: v.extname,
						fileType: v.fileType,
						image: v.image,
						name: v.name,
						path: v.path,
						size: v.size,
						fileID:v.fileID,
						url: v.url,
						// 淇敼鍒犻櫎涓€涓枃浠跺悗涓嶈兘鍐嶄笂浼犵殑bug, #694
            uuid: v.uuid,
            status: v.status,
            cloudPath: v.cloudPath
					})
				})
				return newFilesData
			},
			async getTempFileURL(fileList) {
				fileList = {
					fileList: [].concat(fileList)
				}
				const urls = await uniCloud.getTempFileURL(fileList)
				return urls.fileList[0].tempFileURL || ''
			},
			/**
			 * 鑾峰彇鐖跺厓绱犲疄渚?
			 */
			getForm(name = 'uniForms') {
				let parent = this.$parent;
				let parentName = parent.$options.name;
				while (parentName !== name) {
					parent = parent.$parent;
					if (!parent) return false;
					parentName = parent.$options.name;
				}
				return parent;
			}
		}
	}
</script>

<style>
	.uni-file-picker {
		/* #ifndef APP-NVUE */
		box-sizing: border-box;
		overflow: hidden;
		width: 100%;
		/* #endif */
		flex: 1;
	}

	.uni-file-picker__header {
		padding-top: 5px;
		padding-bottom: 10px;
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		justify-content: space-between;
	}

	.file-title {
		font-size: 14px;
		color: #333;
	}

	.file-count {
		font-size: 14px;
		color: #999;
	}

	.is-add {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		align-items: center;
		justify-content: center;
	}

	.icon-add {
		width: 50px;
		height: 5px;
		background-color: #f1f1f1;
		border-radius: 2px;
	}

	.rotate {
		position: absolute;
		transform: rotate(90deg);
	}
</style>

