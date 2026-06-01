<template>
	<view class="uni-datetime-picker">
		<view @click="initTimePicker">
			<slot>
				<view class="uni-datetime-picker-timebox-pointer"
					:class="{'uni-datetime-picker-disabled': disabled, 'uni-datetime-picker-timebox': border}">
					<text class="uni-datetime-picker-text">{{time}}</text>
					<view v-if="!time" class="uni-datetime-picker-time">
						<text class="uni-datetime-picker-text">{{selectTimeText}}</text>
					</view>
				</view>
			</slot>
		</view>
		<view v-if="visible" id="mask" class="uni-datetime-picker-mask" @click="tiggerTimePicker"></view>
		<view v-if="visible" class="uni-datetime-picker-popup" :class="[dateShow && timeShow ? '' : 'fix-nvue-height']"
			:style="fixNvueBug">
			<view class="uni-title">
				<text class="uni-datetime-picker-text">{{selectTimeText}}</text>
			</view>
			<view v-if="dateShow" class="uni-datetime-picker__container-box">
				<picker-view class="uni-datetime-picker-view" :indicator-style="indicatorStyle" :value="ymd"
					@change="bindDateChange">
					<picker-view-column>
						<view class="uni-datetime-picker-item" v-for="(item,index) in years" :key="index">
							<text class="uni-datetime-picker-item">{{lessThanTen(item)}}</text>
						</view>
					</picker-view-column>
					<picker-view-column>
						<view class="uni-datetime-picker-item" v-for="(item,index) in months" :key="index">
							<text class="uni-datetime-picker-item">{{lessThanTen(item)}}</text>
						</view>
					</picker-view-column>
					<picker-view-column>
						<view class="uni-datetime-picker-item" v-for="(item,index) in days" :key="index">
							<text class="uni-datetime-picker-item">{{lessThanTen(item)}}</text>
						</view>
					</picker-view-column>
				</picker-view>
				<!-- 鍏煎 nvue 涓嶆敮鎸佷吉绫?-->
				<text class="uni-datetime-picker-sign sign-left">-</text>
				<text class="uni-datetime-picker-sign sign-right">-</text>
			</view>
			<view v-if="timeShow" class="uni-datetime-picker__container-box">
				<picker-view class="uni-datetime-picker-view" :class="[hideSecond ? 'time-hide-second' : '']"
					:indicator-style="indicatorStyle" :value="hms" @change="bindTimeChange">
					<picker-view-column>
						<view class="uni-datetime-picker-item" v-for="(item,index) in hours" :key="index">
							<text class="uni-datetime-picker-item">{{lessThanTen(item)}}</text>
						</view>
					</picker-view-column>
					<picker-view-column>
						<view class="uni-datetime-picker-item" v-for="(item,index) in minutes" :key="index">
							<text class="uni-datetime-picker-item">{{lessThanTen(item)}}</text>
						</view>
					</picker-view-column>
					<picker-view-column v-if="!hideSecond">
						<view class="uni-datetime-picker-item" v-for="(item,index) in seconds" :key="index">
							<text class="uni-datetime-picker-item">{{lessThanTen(item)}}</text>
						</view>
					</picker-view-column>
				</picker-view>
				<!-- 鍏煎 nvue 涓嶆敮鎸佷吉绫?-->
				<text class="uni-datetime-picker-sign" :class="[hideSecond ? 'sign-center' : 'sign-left']">:</text>
				<text v-if="!hideSecond" class="uni-datetime-picker-sign sign-right">:</text>
			</view>
			<view class="uni-datetime-picker-btn">
				<view @click="clearTime">
					<text class="uni-datetime-picker-btn-text">{{clearText}}</text>
				</view>
				<view class="uni-datetime-picker-btn-group">
					<view class="uni-datetime-picker-cancel" @click="tiggerTimePicker">
						<text class="uni-datetime-picker-btn-text">{{cancelText}}</text>
					</view>
					<view @click="setTime">
						<text class="uni-datetime-picker-btn-text">{{okText}}</text>
					</view>
				</view>
			</view>
		</view>
	</view>
</template>

<script>
	import {
		initVueI18n
	} from '@dcloudio/uni-i18n'
	import i18nMessages from './i18n/index.js'
	const {
		t
	} = initVueI18n(i18nMessages)
	import {
		fixIosDateFormat
	} from './util'

	/**
	 * DatetimePicker 鏃堕棿閫夋嫨鍣?
	 * @description 鍙互鍚屾椂閫夋嫨鏃ユ湡鍜屾椂闂寸殑閫夋嫨鍣?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=xxx
	 * @property {String} type = [datetime | date | time] 鏄剧ず妯″紡
	 * @property {Boolean} multiple = [true|false] 鏄惁澶氶€?
	 * @property {String|Number} value 榛樿鍊?
	 * @property {String|Number} start 璧峰鏃ユ湡鎴栨椂闂?
	 * @property {String|Number} end 璧峰鏃ユ湡鎴栨椂闂?
	 * @property {String} return-type = [timestamp | string]
	 * @event {Function} change  閫変腑鍙戠敓鍙樺寲瑙﹀彂
	 */

	export default {
		name: 'UniDatetimePicker',
		data() {
			return {
				indicatorStyle: `height: 50px;`,
				visible: false,
				fixNvueBug: {},
				dateShow: true,
				timeShow: true,
				title: '鏃ユ湡鍜屾椂闂?,
				// 杈撳叆妗嗗綋鍓嶆椂闂?
				time: '',
				// 褰撳墠鐨勫勾鏈堟棩鏃跺垎绉?
				year: 1920,
				month: 0,
				day: 0,
				hour: 0,
				minute: 0,
				second: 0,
				// 璧峰鏃堕棿
				startYear: 1920,
				startMonth: 1,
				startDay: 1,
				startHour: 0,
				startMinute: 0,
				startSecond: 0,
				// 缁撴潫鏃堕棿
				endYear: 2120,
				endMonth: 12,
				endDay: 31,
				endHour: 23,
				endMinute: 59,
				endSecond: 59,
			}
		},
		options: {
			// #ifdef MP-TOUTIAO
			virtualHost: false,
			// #endif
			// #ifndef MP-TOUTIAO
			virtualHost: true
			// #endif
		},
		props: {
			type: {
				type: String,
				default: 'datetime'
			},
			value: {
				type: [String, Number],
				default: ''
			},
			modelValue: {
				type: [String, Number],
				default: ''
			},
			start: {
				type: [Number, String],
				default: ''
			},
			end: {
				type: [Number, String],
				default: ''
			},
			returnType: {
				type: String,
				default: 'string'
			},
			disabled: {
				type: [Boolean, String],
				default: false
			},
			border: {
				type: [Boolean, String],
				default: true
			},
			hideSecond: {
				type: [Boolean, String],
				default: false
			}
		},
		watch: {
			// #ifndef VUE3
			value: {
				handler(newVal) {
					if (newVal) {
						this.parseValue(fixIosDateFormat(newVal))
						this.initTime(false)
					} else {
						this.time = ''
						this.parseValue(Date.now())
					}
				},
				immediate: true
			},
			// #endif
			// #ifdef VUE3
			modelValue: {
				handler(newVal) {
					if (newVal) {
						this.parseValue(fixIosDateFormat(newVal))
						this.initTime(false)
					} else {
						this.time = ''
						this.parseValue(Date.now())
					}
				},
				immediate: true
			},
			// #endif
			type: {
				handler(newValue) {
					if (newValue === 'date') {
						this.dateShow = true
						this.timeShow = false
						this.title = '鏃ユ湡'
					} else if (newValue === 'time') {
						this.dateShow = false
						this.timeShow = true
						this.title = '鏃堕棿'
					} else {
						this.dateShow = true
						this.timeShow = true
						this.title = '鏃ユ湡鍜屾椂闂?
					}
				},
				immediate: true
			},
			start: {
				handler(newVal) {
					this.parseDatetimeRange(fixIosDateFormat(newVal), 'start')
				},
				immediate: true
			},
			end: {
				handler(newVal) {
					this.parseDatetimeRange(fixIosDateFormat(newVal), 'end')
				},
				immediate: true
			},

			// 鏈堛€佹棩銆佹椂銆佸垎銆佺鍙€夎寖鍥村彉鍖栧悗锛屾鏌ュ綋鍓嶅€兼槸鍚﹀湪鑼冨洿鍐咃紝涓嶅湪鍒欏綋鍓嶅€奸噸缃负鍙€夎寖鍥寸涓€椤?
			months(newVal) {
				this.checkValue('month', this.month, newVal)
			},
			days(newVal) {
				this.checkValue('day', this.day, newVal)
			},
			hours(newVal) {
				this.checkValue('hour', this.hour, newVal)
			},
			minutes(newVal) {
				this.checkValue('minute', this.minute, newVal)
			},
			seconds(newVal) {
				this.checkValue('second', this.second, newVal)
			}
		},
		computed: {
			// 褰撳墠骞淬€佹湀銆佹棩銆佹椂銆佸垎銆佺閫夋嫨鑼冨洿
			years() {
				return this.getCurrentRange('year')
			},

			months() {
				return this.getCurrentRange('month')
			},

			days() {
				return this.getCurrentRange('day')
			},

			hours() {
				return this.getCurrentRange('hour')
			},

			minutes() {
				return this.getCurrentRange('minute')
			},

			seconds() {
				return this.getCurrentRange('second')
			},

			// picker 褰撳墠鍊兼暟缁?
			ymd() {
				return [this.year - this.minYear, this.month - this.minMonth, this.day - this.minDay]
			},
			hms() {
				return [this.hour - this.minHour, this.minute - this.minMinute, this.second - this.minSecond]
			},

			// 褰撳墠 date 鏄?start
			currentDateIsStart() {
				return this.year === this.startYear && this.month === this.startMonth && this.day === this.startDay
			},

			// 褰撳墠 date 鏄?end
			currentDateIsEnd() {
				return this.year === this.endYear && this.month === this.endMonth && this.day === this.endDay
			},

			// 褰撳墠骞淬€佹湀銆佹棩銆佹椂銆佸垎銆佺鐨勬渶灏忓€煎拰鏈€澶у€?
			minYear() {
				return this.startYear
			},
			maxYear() {
				return this.endYear
			},
			minMonth() {
				if (this.year === this.startYear) {
					return this.startMonth
				} else {
					return 1
				}
			},
			maxMonth() {
				if (this.year === this.endYear) {
					return this.endMonth
				} else {
					return 12
				}
			},
			minDay() {
				if (this.year === this.startYear && this.month === this.startMonth) {
					return this.startDay
				} else {
					return 1
				}
			},
			maxDay() {
				if (this.year === this.endYear && this.month === this.endMonth) {
					return this.endDay
				} else {
					return this.daysInMonth(this.year, this.month)
				}
			},
			minHour() {
				if (this.type === 'datetime') {
					if (this.currentDateIsStart) {
						return this.startHour
					} else {
						return 0
					}
				}
				if (this.type === 'time') {
					return this.startHour
				}
			},
			maxHour() {
				if (this.type === 'datetime') {
					if (this.currentDateIsEnd) {
						return this.endHour
					} else {
						return 23
					}
				}
				if (this.type === 'time') {
					return this.endHour
				}
			},
			minMinute() {
				if (this.type === 'datetime') {
					if (this.currentDateIsStart && this.hour === this.startHour) {
						return this.startMinute
					} else {
						return 0
					}
				}
				if (this.type === 'time') {
					if (this.hour === this.startHour) {
						return this.startMinute
					} else {
						return 0
					}
				}
			},
			maxMinute() {
				if (this.type === 'datetime') {
					if (this.currentDateIsEnd && this.hour === this.endHour) {
						return this.endMinute
					} else {
						return 59
					}
				}
				if (this.type === 'time') {
					if (this.hour === this.endHour) {
						return this.endMinute
					} else {
						return 59
					}
				}
			},
			minSecond() {
				if (this.type === 'datetime') {
					if (this.currentDateIsStart && this.hour === this.startHour && this.minute === this.startMinute) {
						return this.startSecond
					} else {
						return 0
					}
				}
				if (this.type === 'time') {
					if (this.hour === this.startHour && this.minute === this.startMinute) {
						return this.startSecond
					} else {
						return 0
					}
				}
			},
			maxSecond() {
				if (this.type === 'datetime') {
					if (this.currentDateIsEnd && this.hour === this.endHour && this.minute === this.endMinute) {
						return this.endSecond
					} else {
						return 59
					}
				}
				if (this.type === 'time') {
					if (this.hour === this.endHour && this.minute === this.endMinute) {
						return this.endSecond
					} else {
						return 59
					}
				}
			},

			/**
			 * for i18n
			 */
			selectTimeText() {
				return t("uni-datetime-picker.selectTime")
			},
			okText() {
				return t("uni-datetime-picker.ok")
			},
			clearText() {
				return t("uni-datetime-picker.clear")
			},
			cancelText() {
				return t("uni-datetime-picker.cancel")
			}
		},

		mounted() {
			// #ifdef APP-NVUE
			const res = uni.getSystemInfoSync();
			this.fixNvueBug = {
				top: res.windowHeight / 2,
				left: res.windowWidth / 2
			}
			// #endif
		},

		methods: {
			/**
			 * @param {Object} item
			 * 灏忎簬 10 鍦ㄥ墠闈㈠姞涓?0
			 */

			lessThanTen(item) {
				return item < 10 ? '0' + item : item
			},

			/**
			 * 瑙ｆ瀽鏃跺垎绉掑瓧绗︿覆锛屼緥濡傦細00:00:00
			 * @param {String} timeString
			 */
			parseTimeType(timeString) {
				if (timeString) {
					let timeArr = timeString.split(':')
					this.hour = Number(timeArr[0])
					this.minute = Number(timeArr[1])
					this.second = Number(timeArr[2])
				}
			},

			/**
			 * 瑙ｆ瀽閫夋嫨鍣ㄥ垵濮嬪€硷紝绫诲瀷鍙互鏄瓧绗︿覆銆佹椂闂存埑锛屼緥濡傦細2000-10-02銆?08:30:00'銆?1610695109000
			 * @param {String | Number} datetime
			 */
			initPickerValue(datetime) {
				let defaultValue = null
				if (datetime) {
					defaultValue = this.compareValueWithStartAndEnd(datetime, this.start, this.end)
				} else {
					defaultValue = Date.now()
					defaultValue = this.compareValueWithStartAndEnd(defaultValue, this.start, this.end)
				}
				this.parseValue(defaultValue)
			},

			/**
			 * 鍒濆鍊艰鍒欙細
			 * - 鐢ㄦ埛璁剧疆鍒濆鍊?value
			 * 	- 璁剧疆浜嗚捣濮嬫椂闂?start銆佺粓姝㈡椂闂?end锛屽苟 start < value < end锛屽垵濮嬪€间负 value锛?鍚﹀垯鍒濆鍊间负 start
			 * 	- 鍙缃簡璧峰鏃堕棿 start锛屽苟 start < value锛屽垵濮嬪€间负 value锛屽惁鍒欏垵濮嬪€间负 start
			 * 	- 鍙缃簡缁堟鏃堕棿 end锛屽苟 value < end锛屽垵濮嬪€间负 value锛屽惁鍒欏垵濮嬪€间负 end
			 * 	- 鏃犺捣濮嬬粓姝㈡椂闂达紝鍒欏垵濮嬪€间负 value
			 * - 鏃犲垵濮嬪€?value锛屽垯鍒濆鍊间负褰撳墠鏈湴鏃堕棿 Date.now()
			 * @param {Object} value
			 * @param {Object} dateBase
			 */
			compareValueWithStartAndEnd(value, start, end) {
				let winner = null
				value = this.superTimeStamp(value)
				start = this.superTimeStamp(start)
				end = this.superTimeStamp(end)

				if (start && end) {
					if (value < start) {
						winner = new Date(start)
					} else if (value > end) {
						winner = new Date(end)
					} else {
						winner = new Date(value)
					}
				} else if (start && !end) {
					winner = start <= value ? new Date(value) : new Date(start)
				} else if (!start && end) {
					winner = value <= end ? new Date(value) : new Date(end)
				} else {
					winner = new Date(value)
				}

				return winner
			},

			/**
			 * 杞崲涓哄彲姣旇緝鐨勬椂闂存埑锛屾帴鍙楁棩鏈熴€佹椂鍒嗙銆佹椂闂存埑
			 * @param {Object} value
			 */
			superTimeStamp(value) {
				let dateBase = ''
				if (this.type === 'time' && value && typeof value === 'string') {
					const now = new Date()
					const year = now.getFullYear()
					const month = now.getMonth() + 1
					const day = now.getDate()
					dateBase = year + '/' + month + '/' + day + ' '
				}
				if (Number(value)) {
					value = parseInt(value)
					dateBase = 0
				}
				return this.createTimeStamp(dateBase + value)
			},

			/**
			 * 瑙ｆ瀽榛樿鍊?value锛屽瓧绗︿覆銆佹椂闂存埑
			 * @param {Object} defaultTime
			 */
			parseValue(value) {
				if (!value) {
					return
				}
				if (this.type === 'time' && typeof value === "string") {
					this.parseTimeType(value)
				} else {
					let defaultDate = null
					defaultDate = new Date(value)
					if (this.type !== 'time') {
						this.year = defaultDate.getFullYear()
						this.month = defaultDate.getMonth() + 1
						this.day = defaultDate.getDate()
					}
					if (this.type !== 'date') {
						this.hour = defaultDate.getHours()
						this.minute = defaultDate.getMinutes()
						this.second = defaultDate.getSeconds()
					}
				}
				if (this.hideSecond) {
					this.second = 0
				}
			},

			/**
			 * 瑙ｆ瀽鍙€夋嫨鏃堕棿鑼冨洿 start銆乪nd锛屽勾鏈堟棩瀛楃涓层€佹椂闂存埑
			 * @param {Object} defaultTime
			 */
			parseDatetimeRange(point, pointType) {
				// 鏃堕棿涓虹┖锛屽垯閲嶇疆涓哄垵濮嬪€?
				if (!point) {
					if (pointType === 'start') {
						this.startYear = 1920
						this.startMonth = 1
						this.startDay = 1
						this.startHour = 0
						this.startMinute = 0
						this.startSecond = 0
					}
					if (pointType === 'end') {
						this.endYear = 2120
						this.endMonth = 12
						this.endDay = 31
						this.endHour = 23
						this.endMinute = 59
						this.endSecond = 59
					}
					return
				}
				if (this.type === 'time') {
					const pointArr = point.split(':')
					this[pointType + 'Hour'] = Number(pointArr[0])
					this[pointType + 'Minute'] = Number(pointArr[1])
					this[pointType + 'Second'] = Number(pointArr[2])
				} else {
					if (!point) {
						pointType === 'start' ? this.startYear = this.year - 60 : this.endYear = this.year + 60
						return
					}
					if (Number(point)) {
						point = parseInt(point)
					}
					// datetime 鐨?end 娌℃湁鏃跺垎绉? 鍒欎笉闄愬埗
					const hasTime = /[0-9]:[0-9]/
					if (this.type === 'datetime' && pointType === 'end' && typeof point === 'string' && !hasTime.test(
							point)) {
						point = point + ' 23:59:59'
					}
					const pointDate = new Date(point)
					this[pointType + 'Year'] = pointDate.getFullYear()
					this[pointType + 'Month'] = pointDate.getMonth() + 1
					this[pointType + 'Day'] = pointDate.getDate()
					if (this.type === 'datetime') {
						this[pointType + 'Hour'] = pointDate.getHours()
						this[pointType + 'Minute'] = pointDate.getMinutes()
						this[pointType + 'Second'] = pointDate.getSeconds()
					}
				}
			},

			// 鑾峰彇 骞淬€佹湀銆佹棩銆佹椂銆佸垎銆佺 褰撳墠鍙€夎寖鍥?
			getCurrentRange(value) {
				const range = []
				for (let i = this['min' + this.capitalize(value)]; i <= this['max' + this.capitalize(value)]; i++) {
					range.push(i)
				}
				return range
			},

			// 瀛楃涓查瀛楁瘝澶у啓
			capitalize(str) {
				return str.charAt(0).toUpperCase() + str.slice(1)
			},

			// 妫€鏌ュ綋鍓嶅€兼槸鍚﹀湪鑼冨洿鍐咃紝涓嶅湪鍒欏綋鍓嶅€奸噸缃负鍙€夎寖鍥寸涓€椤?
			checkValue(name, value, values) {
				if (values.indexOf(value) === -1) {
					this[name] = values[0]
				}
			},

			// 姣忎釜鏈堢殑瀹為檯澶╂暟
			daysInMonth(year, month) { // Use 1 for January, 2 for February, etc.
				return new Date(year, month, 0).getDate();
			},

			/**
			 * 鐢熸垚鏃堕棿鎴?
			 * @param {Object} time
			 */
			createTimeStamp(time) {
				if (!time) return
				if (typeof time === "number") {
					return time
				} else {
					time = time.replace(/-/g, '/')
					if (this.type === 'date') {
						time = time + ' ' + '00:00:00'
					}
					return Date.parse(time)
				}
			},

			/**
			 * 鐢熸垚鏃ユ湡鎴栨椂闂寸殑瀛楃涓?
			 */
			createDomSting() {
				const yymmdd = this.year +
					'-' +
					this.lessThanTen(this.month) +
					'-' +
					this.lessThanTen(this.day)

				let hhmmss = this.lessThanTen(this.hour) +
					':' +
					this.lessThanTen(this.minute)

				if (!this.hideSecond) {
					hhmmss = hhmmss + ':' + this.lessThanTen(this.second)
				}

				if (this.type === 'date') {
					return yymmdd
				} else if (this.type === 'time') {
					return hhmmss
				} else {
					return yymmdd + ' ' + hhmmss
				}
			},

			/**
			 * 鍒濆鍖栬繑鍥炲€硷紝骞舵姏鍑?change 浜嬩欢
			 */
			initTime(emit = true) {
				this.time = this.createDomSting()
				if (!emit) return
				if (this.returnType === 'timestamp' && this.type !== 'time') {
					this.$emit('change', this.createTimeStamp(this.time))
					this.$emit('input', this.createTimeStamp(this.time))
					this.$emit('update:modelValue', this.createTimeStamp(this.time))
				} else {
					this.$emit('change', this.time)
					this.$emit('input', this.time)
					this.$emit('update:modelValue', this.time)
				}
			},

			/**
			 * 鐢ㄦ埛閫夋嫨鏃ユ湡鎴栨椂闂存洿鏂?data
			 * @param {Object} e
			 */
			bindDateChange(e) {
				const val = e.detail.value
				this.year = this.years[val[0]]
				this.month = this.months[val[1]]
				this.day = this.days[val[2]]
			},
			bindTimeChange(e) {
				const val = e.detail.value
				this.hour = this.hours[val[0]]
				this.minute = this.minutes[val[1]]
				this.second = this.seconds[val[2]]
			},

			/**
			 * 鍒濆鍖栧脊鍑哄眰
			 */
			initTimePicker() {
				if (this.disabled) return
				const value = fixIosDateFormat(this.time)
				this.initPickerValue(value)
				this.visible = !this.visible
			},

			/**
			 * 瑙﹀彂鎴栧叧闂脊妗?
			 */
			tiggerTimePicker(e) {
				this.visible = !this.visible
			},

			/**
			 * 鐢ㄦ埛鐐瑰嚮鈥滄竻绌衡€濇寜閽紝娓呯┖褰撳墠鍊?
			 */
			clearTime() {
				this.time = ''
				this.$emit('change', this.time)
				this.$emit('input', this.time)
				this.$emit('update:modelValue', this.time)
				this.tiggerTimePicker()
			},

			/**
			 * 鐢ㄦ埛鐐瑰嚮鈥滅‘瀹氣€濇寜閽?
			 */
			setTime() {
				this.initTime()
				this.tiggerTimePicker()
			}
		}
	}
</script>

<style lang="scss">
	$uni-primary: #007aff !default;

	.uni-datetime-picker {
		/* #ifndef APP-NVUE */
		/* width: 100%; */
		/* #endif */
	}

	.uni-datetime-picker-view {
		height: 130px;
		width: 270px;
		/* #ifndef APP-NVUE */
		cursor: pointer;
		/* #endif */
	}

	.uni-datetime-picker-item {
		height: 50px;
		line-height: 50px;
		text-align: center;
		font-size: 14px;
	}

	.uni-datetime-picker-btn {
		margin-top: 60px;
		/* #ifndef APP-NVUE */
		display: flex;
		cursor: pointer;
		/* #endif */
		flex-direction: row;
		justify-content: space-between;
	}

	.uni-datetime-picker-btn-text {
		font-size: 14px;
		color: $uni-primary;
	}

	.uni-datetime-picker-btn-group {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
	}

	.uni-datetime-picker-cancel {
		margin-right: 30px;
	}

	.uni-datetime-picker-mask {
		position: fixed;
		bottom: 0px;
		top: 0px;
		left: 0px;
		right: 0px;
		background-color: rgba(0, 0, 0, 0.4);
		transition-duration: 0.3s;
		z-index: 998;
	}

	.uni-datetime-picker-popup {
		border-radius: 8px;
		padding: 30px;
		width: 270px;
		/* #ifdef APP-NVUE */
		height: 500px;
		/* #endif */
		/* #ifdef APP-NVUE */
		width: 330px;
		/* #endif */
		background-color: #fff;
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		transition-duration: 0.3s;
		z-index: 999;
	}

	.fix-nvue-height {
		/* #ifdef APP-NVUE */
		height: 330px;
		/* #endif */
	}

	.uni-datetime-picker-time {
		color: grey;
	}

	.uni-datetime-picker-column {
		height: 50px;
	}

	.uni-datetime-picker-timebox {

		border: 1px solid #E5E5E5;
		border-radius: 5px;
		padding: 7px 10px;
		/* #ifndef APP-NVUE */
		box-sizing: border-box;
		cursor: pointer;
		/* #endif */
	}

	.uni-datetime-picker-timebox-pointer {
		/* #ifndef APP-NVUE */
		cursor: pointer;
		/* #endif */
	}


	.uni-datetime-picker-disabled {
		opacity: 0.4;
		/* #ifdef H5 */
		cursor: not-allowed !important;
		/* #endif */
	}

	.uni-datetime-picker-text {
		font-size: 14px;
		line-height: 50px
	}

	.uni-datetime-picker-sign {
		position: absolute;
		top: 53px;
		/* 鍑忔帀 10px 鐨勫厓绱犻珮搴︼紝鍏煎nvue */
		color: #999;
		/* #ifdef APP-NVUE */
		font-size: 16px;
		/* #endif */
	}

	.sign-left {
		left: 86px;
	}

	.sign-right {
		right: 86px;
	}

	.sign-center {
		left: 135px;
	}

	.uni-datetime-picker__container-box {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-top: 40px;
	}

	.time-hide-second {
		width: 180px;
	}
</style>

