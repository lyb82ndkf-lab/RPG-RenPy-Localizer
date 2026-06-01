<template>
  <view class="uni-data-pickerview">
    <scroll-view v-if="!isCloudDataList" class="selected-area" scroll-x="true">
      <view class="selected-list">
          <view 
            class="selected-item"
            v-for="(item,index) in selected"
            :key="index"
            :class="{
              'selected-item-active':index == selectedIndex
            }"
            @click="handleSelect(index)"
          >
            <text>{{item.text || ''}}</text>
          </view>
      </view>
    </scroll-view>
    <view class="tab-c">
      <scroll-view class="list" :scroll-y="true">
        <view class="item" :class="{'is-disabled': !!item.disable}" v-for="(item, j) in dataList[selectedIndex]" :key="j"
          @click="handleNodeClick(item, selectedIndex, j)">
          <text class="item-text">{{item[map.text]}}</text>
          <view class="check" v-if="selected.length > selectedIndex && item[map.value] == selected[selectedIndex].value"></view>
        </view>
      </scroll-view>

      <view class="loading-cover" v-if="loading">
        <uni-load-more class="load-more" :contentText="loadMore" status="loading"></uni-load-more>
      </view>
      <view class="error-message" v-if="errorMessage">
        <text class="error-text">{{errorMessage}}</text>
      </view>
    </view>
  </view>
</template>

<script>
  import dataPicker from "./uni-data-picker.js"

  /**
   * DataPickerview
   * @description uni-data-pickerview
   * @tutorial https://ext.dcloud.net.cn/plugin?id=3796
   * @property {Array} localdata 鏈湴鏁版嵁锛屽弬鑰?
   * @property {Boolean} step-searh = [true|false] 鏄惁鍒嗗竷鏌ヨ
   * @value true 鍚敤鍒嗗竷鏌ヨ锛屼粎鏌ヨ褰撳墠閫変腑鑺傜偣
   * @value false 鍏抽棴鍒嗗竷鏌ヨ锛屼竴娆℃煡璇㈠嚭鎵€鏈夋暟鎹?
   * @property {String|DBFieldString} self-field 鍒嗗竷鏌ヨ褰撳墠瀛楁鍚嶇О
   * @property {String|DBFieldString} parent-field 鍒嗗竷鏌ヨ鐖跺瓧娈靛悕绉?
   * @property {String|DBCollectionString} collection 琛ㄥ悕
   * @property {String|DBFieldString} field 鏌ヨ瀛楁锛屽涓瓧娈电敤 `,` 鍒嗗壊
   * @property {String} orderby 鎺掑簭瀛楁鍙婃搴忓€掑彊璁剧疆
   * @property {String|JQLString} where 鏌ヨ鏉′欢
   */
  export default {
    name: 'UniDataPickerView',
    emits: ['nodeclick', 'change', 'datachange', 'update:modelValue'],
    mixins: [dataPicker],
    props: {
      managedMode: {
        type: Boolean,
        default: false
      },
      ellipsis: {
        type: Boolean,
        default: true
      }
    },
    created() {
      if (!this.managedMode) {
        this.$nextTick(() => {
          this.loadData();
        })
      }
    },
    methods: {
      onPropsChange() {
        this._treeData = [];
        this.selectedIndex = 0;
        this.$nextTick(() => {
          this.loadData();
        })
      },
      handleSelect(index) {
        this.selectedIndex = index;
      },
      handleNodeClick(item, i, j) {
        if (item.disable) {
          return;
        }

        const node = this.dataList[i][j];
        const text = node[this.map.text];
        const value = node[this.map.value];

        if (i < this.selected.length - 1) {
          this.selected.splice(i, this.selected.length - i)
          this.selected.push({
            text,
            value
          })
        } else if (i === this.selected.length - 1) {
          this.selected.splice(i, 1, {
            text,
            value
          })
        }

        if (node.isleaf) {
          this.onSelectedChange(node, node.isleaf)
          return
        }

        const {
          isleaf,
          hasNodes
        } = this._updateBindData()

        // 鏈湴鏁版嵁
        if (this.isLocalData) {
          this.onSelectedChange(node, (!hasNodes || isleaf))
        } else if (this.isCloudDataList) { // Cloud 鏁版嵁 (鍗曞垪)
          this.onSelectedChange(node, true)
        } else if (this.isCloudDataTree) { // Cloud 鏁版嵁 (鏍戝舰)
          if (isleaf) {
            this.onSelectedChange(node, node.isleaf)
          } else if (!hasNodes) { // 璇锋眰涓€娆℃湇鍔″櫒浠ョ‘瀹氭槸鍚︿负鍙跺瓙鑺傜偣
            this.loadCloudDataNode((data) => {
              if (!data.length) {
                node.isleaf = true
              } else {
                this._treeData.push(...data)
                this._updateBindData(node)
              }
              this.onSelectedChange(node, node.isleaf)
            })
          }
        }
      },
      updateData(data) {
        this._treeData = data.treeData
        this.selected = data.selected
        if (!this._treeData.length) {
          this.loadData()
        } else {
          //this.selected = data.selected
          this._updateBindData()
        }
      },
      onDataChange() {
        this.$emit('datachange');
      },
      onSelectedChange(node, isleaf) {
        if (isleaf) {
          this._dispatchEvent()
        }

        if (node) {
          this.$emit('nodeclick', node)
        }
      },
      _dispatchEvent() {
        this.$emit('change', this.selected.slice(0))
      }
    }
  }
</script>

<style lang="scss">
	$uni-primary: #007aff !default;

	.uni-data-pickerview {
		flex: 1;
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: column;
		overflow: hidden;
		height: 100%;
	}

  .error-text {
    color: #DD524D;
  }

  .loading-cover {
    position: absolute;
    left: 0;
    top: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(255, 255, 255, .5);
    /* #ifndef APP-NVUE */
    display: flex;
    /* #endif */
    flex-direction: column;
    align-items: center;
    z-index: 1001;
  }

  .load-more {
    /* #ifndef APP-NVUE */
    margin: auto;
    /* #endif */
  }

  .error-message {
    background-color: #fff;
    position: absolute;
    left: 0;
    top: 0;
    right: 0;
    bottom: 0;
    padding: 15px;
    opacity: .9;
    z-index: 102;
  }

  /* #ifdef APP-NVUE */
  .selected-area {
    width: 750rpx;
  }
  /* #endif */

  .selected-list {
    /* #ifndef APP-NVUE */
    display: flex;
    flex-wrap: nowrap;
    /* #endif */
    flex-direction: row;
    padding: 0 5px;
    border-bottom: 1px solid #f8f8f8;
  }

  .selected-item {
    margin-left: 10px;
    margin-right: 10px;
    padding: 12px 0;
    text-align: center;
    /* #ifndef APP-NVUE */
    white-space: nowrap;
    /* #endif */
  }

  .selected-item-text-overflow {
    width: 168px;
    /* fix nvue */
    overflow: hidden;
    /* #ifndef APP-NVUE */
    width: 6em;
    white-space: nowrap;
    text-overflow: ellipsis;
    -o-text-overflow: ellipsis;
    /* #endif */
  }

	.selected-item-active {
		border-bottom: 2px solid $uni-primary;
	}

	.selected-item-text {
		color: $uni-primary;
	}

  .tab-c {
    position: relative;
    flex: 1;
    /* #ifndef APP-NVUE */
    display: flex;
    /* #endif */
    flex-direction: row;
    overflow: hidden;
  }

  .list {
    flex: 1;
  }

  .item {
    padding: 12px 15px;
    /* border-bottom: 1px solid #f0f0f0; */
    /* #ifndef APP-NVUE */
    display: flex;
    /* #endif */
    flex-direction: row;
    justify-content: space-between;
  }

  .is-disabled {
    opacity: .5;
  }

  .item-text {
    /* flex: 1; */
    color: #333333;
  }

  .item-text-overflow {
    width: 280px;
    /* fix nvue */
    overflow: hidden;
    /* #ifndef APP-NVUE */
    width: 20em;
    white-space: nowrap;
    text-overflow: ellipsis;
    -o-text-overflow: ellipsis;
    /* #endif */
  }

	.check {
		margin-right: 5px;
		border: 2px solid $uni-primary;
		border-left: 0;
		border-top: 0;
		height: 12px;
		width: 6px;
		transform-origin: center;
		/* #ifndef APP-NVUE */
		transition: all 0.3s;
		/* #endif */
		transform: rotate(45deg);
	}
</style>

