export default {
    props: {
        svg_content: String,
        snapshot: Object,
        is_running: Boolean,
    },
    data() {
        return {
            svgComponent: null
        }
    },
    watch: {
        svg_content: {
            immediate: true,
            handler(newVal) {
                if (newVal) {
                    this.svgComponent = {
                        template: `<div class="svg-vue-wrapper" style="width: 100%; height: 100%; display: flex;">${newVal}</div>`,
                        props: ['snapshot'],
                        methods: {
                            getPvColor(pvKey, spKey, normalColor) {
                                if (!this.snapshot) return normalColor;
                                const pvStr = this.snapshot[pvKey];
                                const spStr = this.snapshot[spKey];
                                if (pvStr === undefined || spStr === undefined) return normalColor;
                                
                                const pv = parseFloat(pvStr);
                                const sp = parseFloat(spStr);
                                if (isNaN(pv) || isNaN(sp)) return normalColor;
                                
                                const diff = Math.abs(pv - sp);
                                const absSp = Math.abs(sp);
                                
                                if (diff > 0.05 * absSp) return '#FF0000'; // red
                                if (diff > 0.01 * absSp) return '#FFC000'; // yellow
                                return normalColor;
                            }
                        }
                    }
                }
            }
        }
    },
    template: `
        <component v-if="svgComponent" :is="svgComponent" :snapshot="snapshot" :class="{'pid-animation-running': is_running}"></component>
    `
}
