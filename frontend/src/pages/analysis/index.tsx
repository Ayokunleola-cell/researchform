// src/pages/analysis/index.tsx

import React, { useEffect, useState, useCallback } from 'react';
import ReactDOM from 'react-dom';
import Cookies from 'js-cookie';

import AppLayout from '../../components/layout/AppLayout';

import ResearchWorkflow from '../../components/ui/ResearchWorkflow';

import EmptyState from '../../components/ui/EmptyState';

import { useDropzone } from 'react-dropzone';

import { analysisApi, surveysApi, questionsApi } from '../../lib/api';

import {

  importMarketplaceDataset,

  briefFromMarketplaceDataset,

  MarketplaceImportError,

} from '../../lib/marketplaceAnalysis';

import { creditsApi, type CreditEstimate } from '../../lib/api';

import AnalysisCostBanner from '../../components/analysis/AnalysisCostBanner';

import Link from 'next/link';

import { useRouter } from 'next/router';

import useSWR from 'swr';

import { RiArrowUpSFill, RiFileUploadFill, RiBubbleChartFill, RiLineChartFill, RiFlaskFill, RiClipboardFill, RiCloseFill, RiArrowRightSFill, RiSparklingFill, RiSearchEyeFill, RiBookOpenFill, RiArrowRightFill, RiGroupFill, RiFileTextFill, RiHashtag, RiAlertFill, RiTimeFill, RiRecordCircleFill, RiMicroscopeFill, RiLoader4Line, RiFocus2Fill, RiPulseFill, RiFileExcelFill, RiBrainFill, RiFileFill, RiDragDropFill, RiFlashlightFill, RiArrowLeftFill, RiStackFill, RiCheckboxCircleFill, RiDatabase2Fill, RiMessage2Fill, RiPieChartFill, RiAddFill, RiArrowDownSFill, RiUpload2Fill, RiBarChart2Fill, RiErrorWarningFill, RiDeleteBinFill, RiMapFill, RiGraduationCapFill, RiCpuFill, RiBarChartFill, RiRefreshLine, RiProjectorFill } from 'react-icons/ri';

import toast from 'react-hot-toast';

import clsx from 'clsx';



// ─── Status map ───────────────────────────────────────────────────────

const STATUS_MAP: Record<string, { label: string; cls: string }> = {

  pending:                        { label: 'Pending',                cls: 'badge-neutral'  },

  assembling:                     { label: 'Assembling',             cls: 'badge-brand'    },

  cleaning:                       { label: 'Cleaning',               cls: 'badge-brand'    },

  inspecting:                     { label: 'Inspecting',             cls: 'badge-brand'    },

  awaiting_preprocessing_choice:  { label: 'Choose Preprocessing',  cls: 'badge-warning'  },

  decoding:                       { label: 'Decoding',               cls: 'badge-brand'    },

  decode_review:                  { label: 'Review Required',        cls: 'badge-warning'  },

  parsing:                        { label: 'Analysing',              cls: 'badge-brand'    },

  selecting:                      { label: 'Selecting Tests',        cls: 'badge-brand'    },

  generating:                     { label: 'Generating',             cls: 'badge-brand'    },

  executing:                      { label: 'Running',                cls: 'badge-brand'    },

  visualising:                    { label: 'Visualising',            cls: 'badge-brand'    },

  thematic_analysis:              { label: 'Thematic Analysis',      cls: 'badge-brand'    },

  writing:                        { label: 'Writing Report',         cls: 'badge-brand'    },

  building:                       { label: 'Building Doc',           cls: 'badge-brand'    },

  complete:                       { label: 'Complete',               cls: 'badge-success'  },

  failed:                         { label: 'Failed',                 cls: 'badge-danger'   },

};





// ─── Statistical Techniques Catalogue ────────────────────────────────

// Each technique declares 'requires' so we can validate against the

// uploaded dataset's data_dictionary before the pipeline runs.

// Requirement fields:

//   minContinuous  – minimum number of continuous columns

//   minOrdinal     – minimum ordinal columns (includes continuous)

//   minNominal     – minimum nominal/categorical columns

//   minCols        – minimum total columns

//   minRows        – minimum row count

//   groupCol       – needs at least one nominal col with 2+ unique values

const TECHNIQUE_GROUPS = [

  // ── Group 1: Descriptive Statistics ──────────────────────────────────

  {

    id: 'descriptive',

    label: 'Descriptive Statistics',

    color: '#6366f1',

    icon: RiBarChart2Fill,

    desc: 'Summarise and describe data features',

    techniques: [

      { id: 'freq_dist',       label: 'Frequency Distribution',           desc: 'Counts and percentages for categorical variables',     requires: { minNominal: 1 } },

      { id: 'freq_analysis',   label: 'Frequency Analysis',               desc: 'Extended frequency with cumulative % and relative freq', requires: { minNominal: 1 } },

      { id: 'freq_dist_3',     label: 'Frequency Distribution Table',     desc: 'Grouped frequency distribution with class intervals',  requires: { minContinuous: 1 } },

      { id: 'central_tend',    label: 'Measures of Central Tendency',     desc: 'Overview of mean, median and mode',                   requires: { minContinuous: 1 } },

      { id: 'dispersion',      label: 'Measures of Dispersion',           desc: 'Standard deviation, variance, range, IQR',            requires: { minContinuous: 1 } },

      { id: 'mean_median_mode',label: 'Finding Mean, Median and Mode',    desc: 'Explicit computation and comparison of all three',    requires: { minContinuous: 1 } },

      { id: 'dispersion_2',    label: 'Measure of Dispersion 2',          desc: 'IQR, semi-interquartile range, Q1-Q3 detail',         requires: { minContinuous: 1 } },

      { id: 'dispersion_3',    label: 'Measure of Dispersion 3',          desc: 'Coefficient of Variation, MAD, range detail',         requires: { minContinuous: 1 } },

      { id: 'percentiles',     label: 'Percentiles',                      desc: 'Q1, Q3 and custom percentile breakdown',              requires: { minContinuous: 1 } },

      { id: 'dispersion_4',    label: 'Measure of Dispersion 4',          desc: 'Variance, standard error, 95% CI for mean',           requires: { minContinuous: 1 } },

      { id: 'percentiles_2',   label: 'Percentiles 2',                    desc: 'Deciles (10th–90th) and 5th/95th percentile',         requires: { minContinuous: 1 } },

      { id: 'percentiles_3',   label: 'Percentiles 3',                    desc: 'Percentile ranks for individual scores',              requires: { minContinuous: 1 } },

      { id: 'z_scores',        label: 'Z-Scores',                         desc: 'Standardised scores for all numeric variables',       requires: { minContinuous: 1 } },

      { id: 'percentiles_4',   label: 'Percentiles 4',                    desc: 'Custom percentile table (5th to 95th)',               requires: { minContinuous: 1 } },

      { id: 'z_scores_2',      label: 'Z-Scores 2',                       desc: 'Z-score interpretation and probability areas',        requires: { minContinuous: 1 } },

      { id: 'z_scores_3',      label: 'Z-Scores 3',                       desc: 'Z-table lookup and normal area calculations',         requires: { minContinuous: 1 } },

      { id: 'crosstab',        label: 'Cross-tabulation',                 desc: 'Two-way tables showing group frequencies',            requires: { minNominal: 2 } },

      { id: 'skew_kurtosis',   label: 'Skewness & Kurtosis',             desc: 'Shape characteristics of distributions',              requires: { minContinuous: 1 } },

    ],

  },

  // ── Group 2: Visualizations ──────────────────────────────────────────

  {

    id: 'visualizations',

    label: 'Visualizations',

    color: '#06b6d4',

    icon: RiBarChartFill,

    desc: 'Charts and graphical representations of data',

    techniques: [

      { id: 'viz_bar',         label: 'Bar Charts',                       desc: 'Frequency bar charts for categorical data',            requires: { minNominal: 1 } },

      { id: 'viz_histogram',   label: 'Histograms',                       desc: 'Distribution histogram for continuous variables',      requires: { minContinuous: 1 } },

      { id: 'viz_pie',         label: 'Pie Chart',                        desc: 'Proportional pie/donut charts for categories',        requires: { minNominal: 1 } },

      { id: 'viz_line',        label: 'Line Graphs',                      desc: 'Sequential or time-series line graph',                requires: { minContinuous: 1 } },

      { id: 'viz_scatter',     label: 'Scatter Plot',                     desc: 'Basic XY scatter for two continuous variables',       requires: { minContinuous: 2 } },

      { id: 'viz_scatter_3',   label: 'Scatter Plot 3',                   desc: 'Grouped scatter coloured by category',                requires: { minContinuous: 2, minNominal: 1 } },

      { id: 'viz_scatter_2',   label: 'Scatter Plot 2',                   desc: 'Scatter plot with regression line overlay',           requires: { minContinuous: 2 } },

      { id: 'viz_boxplot_1',   label: 'Box Plot 1',                       desc: 'Single variable box plot with outliers',              requires: { minContinuous: 1 } },

      { id: 'viz_boxplot_2',   label: 'Box Plot 2',                       desc: 'Grouped box plots for comparison',                    requires: { minContinuous: 1, groupCol: true } },

    ],

  },

  // ── Group 3: Normal Distribution Testing ─────────────────────────────

  {

    id: 'normality',

    label: 'Normal Distribution Testing',

    color: '#8b5cf6',

    icon: RiPulseFill,

    desc: 'Test and assess normality of distributions',

    techniques: [

      { id: 'normal_dist',     label: 'Normal Distribution',              desc: 'Shapiro-Wilk test with full normality assessment',     requires: { minContinuous: 1, minRows: 3 } },

      { id: 'normal_dist_2',   label: 'Normal Distribution 2',            desc: 'Q-Q (quantile-quantile) plot analysis',               requires: { minContinuous: 1 } },

      { id: 'normal_dist_3',   label: 'Normal Distribution 3',            desc: 'Histogram with normal curve overlay',                 requires: { minContinuous: 1 } },

      { id: 'normal_dist_4',   label: 'Normal Distribution 4',            desc: 'Jarque-Bera test for normality',                      requires: { minContinuous: 1, minRows: 10 } },

      { id: 'normal_dist_5',   label: 'Normal Distribution 5',            desc: 'Anderson-Darling test for normality',                 requires: { minContinuous: 1, minRows: 8 } },

      { id: 'normal_dist_6',   label: 'Normal Distribution 6',            desc: "D'Agostino-Pearson omnibus normality test",           requires: { minContinuous: 1, minRows: 8 } },

      { id: 'normal_dist_7',   label: 'Normal Distribution 7',            desc: 'Lilliefors test (K-S with estimated parameters)',     requires: { minContinuous: 1, minRows: 5 } },

      { id: 'normal_dist_8',   label: 'Normal Distribution 8',            desc: 'Normal probability plot (P-P plot)',                  requires: { minContinuous: 1 } },

      { id: 'normal_dist_9',   label: 'Normal Distribution 9',            desc: 'Confidence intervals for normality statistics',       requires: { minContinuous: 1, minRows: 20 } },

      { id: 'normal_dist_10',  label: 'Normal Distribution 10',           desc: 'All-variables normality summary table',               requires: { minContinuous: 2 } },

      { id: 'normal_dist_11',  label: 'Normal Distribution 11',           desc: 'Omnibus test (combined skewness + kurtosis)',         requires: { minContinuous: 1, minRows: 20 } },

      { id: 'normal_dist_12',  label: 'Normal Distribution 12',           desc: 'Robust normality assessment with bootstrapping',      requires: { minContinuous: 1, minRows: 30 } },

      { id: 'parametric_nonparam', label: 'Parametric and Non-Parametric Test', desc: 'Decision guide: choose parametric or non-parametric', requires: { minContinuous: 1 } },

      { id: 'skewness',        label: 'Skewness',                         desc: 'Skewness values for all numeric variables',           requires: { minContinuous: 1 } },

      { id: 'skewness_2',      label: 'Skewness 2',                       desc: 'SE of skewness, z-test for normality via skew',       requires: { minContinuous: 1 } },

      { id: 'skewness_3',      label: 'Skewness 3',                       desc: 'Transformation recommendations for skewed vars',      requires: { minContinuous: 1 } },

      { id: 'kurtosis',        label: 'Kurtosis',                         desc: 'Excess kurtosis (leptokurtic/platykurtic)',            requires: { minContinuous: 1 } },

      { id: 'kurtosis_2',      label: 'Kurtosis 2',                       desc: 'SE of kurtosis, z-test and distribution shape',       requires: { minContinuous: 1 } },

      { id: 'shapiro_wilk',    label: 'Shapiro-Wilk Test',                desc: 'Normality test for samples under n=5000',             requires: { minContinuous: 1, minRows: 3 } },

      { id: 'shapiro_wilk_2',  label: 'Shapiro-Wilk Test 2',             desc: 'All variables Shapiro-Wilk summary table',            requires: { minContinuous: 2 } },

      { id: 'var_transform',   label: 'Non-Normal Variable Transformation', desc: 'Log, square root, Box-Cox transformations',         requires: { minContinuous: 1, minRows: 10 } },

      { id: 'kolmogorov',      label: 'Kolmogorov-Smirnov Test',          desc: 'Normality test for larger samples',                   requires: { minContinuous: 1, minRows: 30 } },

    ],

  },

  // ── Group 4: Outlier Detection ────────────────────────────────────────

  {

    id: 'outliers',

    label: 'Outlier Detection',

    color: '#ef4444',

    icon: RiErrorWarningFill,

    desc: 'Detect and assess univariate and multivariate outliers',

    techniques: [

      { id: 'outliers_univariate',    label: 'Univariate Outliers',          desc: 'IQR fences and boxplot outlier identification',       requires: { minContinuous: 1 } },

      { id: 'outliers_univariate_2',  label: 'Univariate Outliers 2',        desc: 'Z-score method (|z| > 3) outlier detection',          requires: { minContinuous: 1, minRows: 10 } },

      { id: 'outliers_univariate_3',  label: 'Univariate Outliers 3',        desc: 'Grubbs test for most extreme outlier',                requires: { minContinuous: 1, minRows: 5 } },

      { id: 'outliers_univariate_4',  label: 'Univariate Outliers 4',        desc: 'Detailed outlier labeling with case numbers',         requires: { minContinuous: 1 } },

      { id: 'outliers_multivariate',  label: 'Multivariate Outliers',        desc: 'Mahalanobis D² distance for multivariate outliers',   requires: { minContinuous: 2, minRows: 20 } },

      { id: 'outliers_multivariate_2','label': 'Multivariate Outliers 2',    desc: 'PCA-based multivariate outlier detection',            requires: { minContinuous: 3, minRows: 20 } },

      { id: 'outliers_multivariate_3','label': 'Multivariate Outliers 3',    desc: "Cook's distance for influential cases",               requires: { minContinuous: 2, minRows: 20 } },

      { id: 'outliers_multivariate_4','label': 'Multivariate Outliers 4',    desc: 'Leverage (hat values) for influential points',        requires: { minContinuous: 2, minRows: 20 } },

    ],

  },

  // ── Group 5: Hypothesis Testing Concepts ─────────────────────────────

  {

    id: 'hypothesis',

    label: 'Hypothesis Testing',

    color: '#f59e0b',

    icon: RiFocus2Fill,

    desc: 'Hypothesis formulation, testing framework and error types',

    techniques: [

      { id: 'hypothesis',          label: 'Hypothesis',                   desc: 'Hypothesis testing framework: setup and procedure',   requires: { minContinuous: 1 } },

      { id: 'hypothesis_2',        label: 'Hypothesis 2',                 desc: 'Type I & Type II errors, significance levels',        requires: { minContinuous: 1 } },

      { id: 'hypothesis_3',        label: 'Hypothesis 3',                 desc: 'Statistical power and sample size analysis',          requires: { minContinuous: 1, minRows: 20 } },

      { id: 'null_alt_hypothesis', label: 'Null and Alternative Hypothesis',  desc: 'Formulation of H₀ and H₁ for research questions', requires: { minContinuous: 1 } },

      { id: 'null_alt_hypothesis_2','label': 'Null and Alternative Hypothesis 2', desc: 'Decision rules and rejection region setup',    requires: { minContinuous: 1 } },

      { id: 'one_two_tailed',      label: 'One vs Two Tailed Test',       desc: 'Directional vs non-directional hypothesis testing',   requires: { minContinuous: 1 } },

      { id: 'one_two_tailed_2',    label: 'One vs Two Tailed Test 2',     desc: 'Critical regions and rejection zones',                requires: { minContinuous: 1 } },

      { id: 'one_two_tailed_3',    label: 'One vs Two Tailed Test 3',     desc: 'Practical guide with worked examples',                requires: { minContinuous: 1 } },

    ],

  },

  // ── Group 6: Parametric Tests ─────────────────────────────────────────

  {

    id: 'parametric',

    label: 'Parametric Tests',

    color: '#3b82f6',

    icon: RiLineChartFill,

    desc: 'Compare means assuming normal distribution',

    techniques: [

      { id: 'one_sample_t',    label: 'One Sample T-test',                desc: 'Compare group mean against a known value',            requires: { minContinuous: 1, minRows: 5, needsContinuousDV: true } },

      { id: 'one_sample_t_2',  label: 'One Sample T-test 2',              desc: "Cohen's d effect size for one-sample t",             requires: { minContinuous: 1, minRows: 5 } },

      { id: 'one_sample_t_3',  label: 'One Sample T-test 3',              desc: 'CI for the mean',                                     requires: { minContinuous: 1, minRows: 5 } },

      { id: 'one_sample_t_4',  label: 'One Sample T-test 4',              desc: 'Power analysis',                                      requires: { minContinuous: 1 } },

      { id: 'one_sample_t_5',  label: 'One Sample T-test 5',              desc: 'Bootstrap version of one-sample t',                   requires: { minContinuous: 1, minRows: 20 } },

      { id: 'one_sample_t_6',  label: 'One Sample T-test 6',              desc: 'All variables summary table',                         requires: { minContinuous: 2 } },

      { id: 'paired_t',        label: 'Paired Sample T-test',             desc: 'Compare means within the same group (pre/post)',      requires: { minContinuous: 2, minRows: 10, needsPaired: true } },

      { id: 'paired_t_2',      label: 'Paired Sample T-test 2',           desc: "Cohen's d effect size for paired t",                 requires: { minContinuous: 2, minRows: 10, needsPaired: true } },

      { id: 'paired_t_3',      label: 'Paired Sample T-test 3',           desc: 'CI for mean difference',                             requires: { minContinuous: 2, minRows: 10 } },

      { id: 'paired_t_4',      label: 'Paired Sample T-test 4',           desc: 'Normality of differences (Shapiro-Wilk on d)',       requires: { minContinuous: 2, minRows: 10 } },

      { id: 'paired_t_5',      label: 'Paired Sample T-test 5',           desc: 'Full summary with descriptive statistics',           requires: { minContinuous: 2, minRows: 10 } },

      { id: 'independent_t',   label: 'Independent Sample T-test',        desc: 'Compare means of two independent groups',             requires: { minContinuous: 1, groupCol: true, exactGroups: 2, minRows: 20, needsContinuousDV: true } },

      { id: 'independent_t_2', label: 'Independent Sample T-test 2',      desc: "Cohen's d effect size",                              requires: { minContinuous: 1, groupCol: true, minRows: 20 } },

      { id: 'independent_t_3', label: 'Independent Sample T-test 3',      desc: "Levene's test then t-test",                          requires: { minContinuous: 1, groupCol: true, minRows: 20 } },

      { id: 'independent_t_4', label: 'Independent Sample T-test 4',      desc: 'CI for mean difference',                             requires: { minContinuous: 1, groupCol: true, minRows: 20 } },

      { id: 'independent_t_5', label: 'Independent Sample T-test 5',      desc: "Welch's t-test (unequal variances)",                 requires: { minContinuous: 1, groupCol: true, minRows: 20 } },

      { id: 'one_way_anova',   label: 'ANOVA',                            desc: 'One-way ANOVA: F-statistic and p-value',             requires: { minContinuous: 1, groupCol: true, minGroups: 3, minRows: 30, needsContinuousDV: true } },

      { id: 'anova_2',         label: 'ANOVA 2',                          desc: 'Eta-squared effect size',                             requires: { minContinuous: 1, groupCol: true, minGroups: 3, minRows: 30 } },

      { id: 'anova_3',         label: 'ANOVA 3',                          desc: 'Descriptives per group (mean, SD, n)',                requires: { minContinuous: 1, groupCol: true, minGroups: 3, minRows: 30 } },

      { id: 'anova_4',         label: 'ANOVA 4',                          desc: 'Full ANOVA table (SS, df, MS, F)',                    requires: { minContinuous: 1, groupCol: true, minGroups: 3, minRows: 30 } },

      { id: 'anova_5',         label: 'ANOVA 5',                          desc: "Assumption checks (normality + Levene's)",            requires: { minContinuous: 1, groupCol: true, minRows: 20 } },

      { id: 'anova_6',         label: 'ANOVA 6',                          desc: 'Power and sample size analysis',                      requires: { minContinuous: 1, groupCol: true, minRows: 20 } },

      { id: 'anova_7',         label: 'ANOVA 7',                          desc: "Welch's ANOVA (robust to unequal variances)",        requires: { minContinuous: 1, groupCol: true, minRows: 20 } },

      { id: 'two_way_anova',   label: 'Two Way ANOVA',                    desc: 'Two-Way ANOVA with interaction term',                 requires: { minContinuous: 1, minNominal: 2, minRows: 40, needsContinuousDV: true } },

      { id: 'two_way_anova_1', label: 'Two Way ANOVA 1',                  desc: 'Interaction plot (means by groups)',                  requires: { minContinuous: 1, minNominal: 2, minRows: 40 } },

      { id: 'two_way_anova_2', label: 'Two Way ANOVA 2',                  desc: 'Main effects analysis',                               requires: { minContinuous: 1, minNominal: 2, minRows: 40 } },

      { id: 'two_way_anova_3', label: 'Two Way ANOVA 3',                  desc: 'Partial eta-squared effect sizes',                    requires: { minContinuous: 1, minNominal: 2, minRows: 40 } },

      { id: 'two_way_anova_4', label: 'Two Way ANOVA 4',                  desc: 'Cell means table',                                    requires: { minContinuous: 1, minNominal: 2, minRows: 40 } },

      { id: 'two_way_anova_5', label: 'Two Way ANOVA 5',                  desc: 'Simple effects analysis',                             requires: { minContinuous: 1, minNominal: 2, minRows: 40 } },

      { id: 'two_way_anova_6', label: 'Two Way ANOVA 6',                  desc: 'Pairwise comparisons within factor levels',           requires: { minContinuous: 1, minNominal: 2, minRows: 40 } },

      { id: 'levene',          label: 'Levene Test',                      desc: "Levene's test of homogeneity of variance",            requires: { minContinuous: 1, groupCol: true } },

      { id: 'manova',          label: 'MANOVA',                           desc: "MANOVA: Wilks' Lambda test",                          requires: { minContinuous: 2, groupCol: true, minRows: 50, needsContinuousDV: true } },

      { id: 'manova_2',        label: 'MANOVA 2',                         desc: "Pillai's Trace",                                      requires: { minContinuous: 2, groupCol: true, minRows: 50 } },

      { id: 'manova_3',        label: 'MANOVA 3',                         desc: "Hotelling's Trace",                                   requires: { minContinuous: 2, groupCol: true, minRows: 50 } },

      { id: 'manova_4',        label: 'MANOVA 4',                         desc: "Box's M test of covariance equality",                 requires: { minContinuous: 2, groupCol: true, minRows: 50 } },

      { id: 'manova_5',        label: 'MANOVA 5',                         desc: 'Follow-up univariate ANOVAs for each DV',             requires: { minContinuous: 2, groupCol: true, minRows: 50 } },

      { id: 'ancova',          label: 'One Way ANCOVA',                   desc: 'ANOVA with covariate control',                        requires: { minContinuous: 2, groupCol: true, minRows: 30, needsContinuousDV: true } },

      { id: 'repeated_anova',  label: 'Repeated Measures ANOVA',          desc: 'Compare means across multiple time points',           requires: { minRepeated: 3, minRows: 20 } },

      { id: 'welch_anova',     label: "Welch's ANOVA",                    desc: 'One-way ANOVA robust to unequal variances',           requires: { minContinuous: 1, groupCol: true, minRows: 20 } },

    ],

  },

  // ── Group 7: Post-Hoc Tests ───────────────────────────────────────────

  {

    id: 'posthoc',

    label: 'Post-Hoc Tests',

    color: '#10b981',

    icon: RiFlaskFill,

    desc: 'Pairwise comparisons after significant ANOVA',

    techniques: [

      { id: 'posthoc_bonferroni',   label: 'Bonferroni Procedure',       desc: 'Conservative pairwise comparisons',                   requires: { minContinuous: 1, groupCol: true, minRows: 30 } },

      { id: 'posthoc_duncan',       label: "Duncan's Multiple Range Test (MRT)", desc: "Duncan's MRT for pairwise comparisons",        requires: { minContinuous: 1, groupCol: true, minRows: 30 } },

      { id: 'posthoc_dunn',         label: "Dunn's Multiple Comparison", desc: "Dunn's test (non-parametric post-hoc)",               requires: { minOrdinal: 1, groupCol: true, minRows: 15 } },

      { id: 'posthoc_lsd',          label: "Fisher's LSD",               desc: "Fisher's Least Significant Difference",               requires: { minContinuous: 1, groupCol: true, minRows: 30 } },

      { id: 'posthoc_newman_keuls', label: 'Newman-Keuls',               desc: 'Newman-Keuls sequential range test',                  requires: { minContinuous: 1, groupCol: true, minRows: 30 } },

      { id: 'posthoc_scheffe',      label: "Scheffe's Method",           desc: "Most conservative post-hoc test",                     requires: { minContinuous: 1, groupCol: true, minRows: 30 } },

      { id: 'posthoc_tukey',        label: "Tukey's Test",               desc: "Tukey's HSD balanced pairwise comparisons",           requires: { minContinuous: 1, groupCol: true, minRows: 30 } },

      { id: 'posthoc_dunnett',      label: "Dunnett's Correction",       desc: "Compare all groups to a control group",               requires: { minContinuous: 1, groupCol: true, minRows: 30 } },

    ],

  },

  // ── Group 8: Non-Parametric Tests ────────────────────────────────────

  {

    id: 'nonparametric',

    label: 'Non-Parametric Tests',

    color: '#ec4899',

    icon: RiFlaskFill,

    desc: 'Distribution-free alternatives for ordinal/non-normal data',

    techniques: [

      { id: 'mann_whitney',    label: 'Mann Whitney Test',                desc: 'Non-parametric alternative to independent t-test',    requires: { minOrdinal: 1, groupCol: true, exactGroups: 2, minRows: 10 } },

      { id: 'mann_whitney_2',  label: 'Mann Whitney Test 2',              desc: 'Effect size r',                                       requires: { minOrdinal: 1, groupCol: true, minRows: 10 } },

      { id: 'mann_whitney_3',  label: 'Mann Whitney Test 3',              desc: 'CI for median difference',                            requires: { minOrdinal: 1, groupCol: true, minRows: 10 } },

      { id: 'mann_whitney_4',  label: 'Mann Whitney Test 4',              desc: 'All pairwise group combinations',                     requires: { minOrdinal: 1, groupCol: true, minGroups: 3, minRows: 10 } },

      { id: 'friedman',        label: 'Friedman Test',                    desc: 'Non-parametric repeated measures comparison',         requires: { minOrdinal: 3, minRows: 10 } },

      { id: 'friedman_2',      label: 'Friedman Test 2',                  desc: "Kendall's W concordance (effect size)",               requires: { minOrdinal: 3, minRows: 10 } },

      { id: 'wilcoxon',        label: 'Wilcoxon Signed Rank Test',        desc: 'Non-parametric alternative to paired t-test',         requires: { minOrdinal: 2, needsPaired: true, minRows: 10 } },

      { id: 'wilcoxon_2',      label: 'Wilcoxon Signed Rank Test 2',      desc: 'Effect size r',                                       requires: { minOrdinal: 2, minRows: 10 } },

      { id: 'wilcoxon_3',      label: 'Wilcoxon Signed Rank Test 3',      desc: 'CI for median difference',                            requires: { minOrdinal: 2, minRows: 10 } },

      { id: 'kruskal_wallis',  label: 'Kruskal Wallis Test',              desc: 'Non-parametric alternative to one-way ANOVA',         requires: { minOrdinal: 1, groupCol: true, minGroups: 3, minRows: 15 } },

      { id: 'kruskal_wallis_2',label: 'Kruskal Wallis Test 2',            desc: "Eta-squared effect size (η²H)",                       requires: { minOrdinal: 1, groupCol: true, minGroups: 3, minRows: 15 } },

      { id: 'chi_square',      label: 'Chi-Square Test',                  desc: 'Association between two categorical variables',       requires: { minNominal: 2, minRows: 20 } },

      { id: 'chi_square_2',    label: 'Chi-Square Test 2',                desc: "Expected frequencies, residuals, Cramér's V",         requires: { minNominal: 2, minRows: 20 } },

      { id: 'fisher_exact',    label: "Fisher's Exact Test",              desc: 'Chi-square alternative for small cell sizes',         requires: { minNominal: 2 } },

      { id: 'mcnemar',         label: 'McNemar Test',                     desc: 'Change in paired binary outcomes',                    requires: { minNominal: 2, needsPaired: true } },

      { id: 'sign_test',       label: 'Sign Test',                        desc: 'Simple test of median difference',                    requires: { minOrdinal: 1 } },

      { id: 'runs_test',       label: 'Runs Test for Randomness',         desc: 'Tests whether data is randomly distributed',          requires: { minOrdinal: 1 } },

    ],

  },

  // ── Group 9: Correlation & Association ───────────────────────────────

  {

    id: 'correlation',

    label: 'Correlation & Association',

    color: '#10b981',

    icon: RiFocus2Fill,

    desc: 'Measure strength and direction of relationships',

    techniques: [

      { id: 'correlation',     label: 'Correlation',                      desc: 'Correlation matrix overview for all numeric vars',    requires: { minContinuous: 2 } },

      { id: 'correlation_2',   label: 'Correlation 2',                    desc: 'Scatter plot matrix (SPLOM)',                          requires: { minContinuous: 2 } },

      { id: 'correlation_3',   label: 'Correlation 3',                    desc: 'Correlation heatmap with significance markers',       requires: { minContinuous: 2 } },

      { id: 'correlation_4',   label: 'Correlation 4',                    desc: 'Significance testing for all correlation pairs',      requires: { minContinuous: 2 } },

      { id: 'correlation_5',   label: 'Correlation 5',                    desc: 'Effect sizes for all correlation pairs',              requires: { minContinuous: 2 } },

      { id: 'pearson',         label: 'Pearson Correlation 1',            desc: 'Pearson r: linear relationship between two vars',     requires: { minContinuous: 2 } },

      { id: 'pearson_2',       label: 'Pearson Correlation 2',            desc: "CI via Fisher's z transformation",                    requires: { minContinuous: 2, minRows: 10 } },

      { id: 'pearson_3',       label: 'Pearson Correlation 3',            desc: 'Scatter plot with regression line',                   requires: { minContinuous: 2 } },

      { id: 'pearson_4',       label: 'Pearson Correlation 4',            desc: 'Partial Pearson (controlling a third variable)',       requires: { minContinuous: 3 } },

      { id: 'spearman',        label: 'Spearman Rank Correlation 1',      desc: 'Spearman Ï: monotonic relationship',                  requires: { minOrdinal: 2 } },

      { id: 'spearman_2',      label: 'Spearman Rank Correlation 2',      desc: 'Ties correction detail',                              requires: { minOrdinal: 2 } },

      { id: 'spearman_3',      label: 'Spearman Rank Correlation 3',      desc: 'CI for rho',                                          requires: { minOrdinal: 2, minRows: 10 } },

      { id: 'spearman_4',      label: 'Spearman Rank Correlation 4',      desc: 'Comparison with Pearson r',                           requires: { minContinuous: 2 } },

      { id: 'spearman_5',      label: 'Spearman Rank Correlation 5',      desc: 'Monotonic relationship significance test',            requires: { minOrdinal: 2 } },

      { id: 'spearman_6',      label: 'Spearman Rank Correlation 6',      desc: 'Full correlation matrix (all pairs)',                 requires: { minOrdinal: 2 } },

      { id: 'kendall_tau',     label: 'Kendall Tau-B Correlation',        desc: 'Kendall τ-B: rank-based, robust with ties',           requires: { minOrdinal: 2 } },

      { id: 'kendall_tau_2',   label: 'Kendall Tau-B Correlation 2',      desc: 'SE and confidence interval for tau-b',               requires: { minOrdinal: 2, minRows: 10 } },

      { id: 'kendall_tau_3',   label: 'Kendall Tau-B Correlation 3',      desc: 'Concordance and discordance pairs',                   requires: { minOrdinal: 2 } },

      { id: 'point_biserial',  label: 'Point Biserial Correlation 1',     desc: 'Continuous vs dichotomous variable',                  requires: { minContinuous: 1, minNominal: 1 } },

      { id: 'point_biserial_2',label: 'Point Biserial Correlation 2',     desc: 'Effect size r²',                                      requires: { minContinuous: 1, minNominal: 1 } },

      { id: 'point_biserial_3',label: 'Point Biserial Correlation 3',     desc: 'Comparison with Pearson r',                           requires: { minContinuous: 1, minNominal: 1 } },

      { id: 'point_biserial_4',label: 'Point Biserial Correlation 4',     desc: 'CI for r_pb',                                         requires: { minContinuous: 1, minNominal: 1, minRows: 10 } },

      { id: 'point_biserial_5',label: 'Point Biserial Correlation 5',     desc: 'All continuous vs all binary variables',              requires: { minContinuous: 1, minNominal: 1 } },

      { id: 'point_biserial_6',label: 'Point Biserial Correlation 6',     desc: 'Biserial correlation (corrected)',                    requires: { minContinuous: 1, minNominal: 1 } },

      { id: 'param_estimates', label: 'Parameter Estimates',              desc: 'Regression coefficient table with SE, t, CI',         requires: { minContinuous: 2, minRows: 20 } },

      { id: 'phi_coeff',       label: 'Phi Coefficient (φ)',              desc: 'Association between two binary variables',            requires: { minNominal: 2 } },

      { id: 'cramers_v',       label: "Cramér's V",                       desc: 'Strength of association in chi-square tables',        requires: { minNominal: 2 } },

      { id: 'partial_corr',    label: 'Partial Correlation',              desc: 'Correlation controlling for a third variable',        requires: { minContinuous: 3 } },

      { id: 'canonical_corr',  label: 'Canonical Correlation',            desc: 'Relationship between two sets of variables',          requires: { minContinuous: 4 } },

    ],

  },

  // ── Group 10: Regression Analysis ────────────────────────────────────

  {

    id: 'regression',

    label: 'Regression Analysis',

    color: '#f59e0b',

    icon: RiLineChartFill,

    desc: 'Model relationships and make predictions',

    techniques: [

      { id: 'simple_linear',    label: 'Simple Linear Regression',        desc: 'One predictor → one continuous outcome',              requires: { minContinuous: 2, minRows: 20, needsContinuousDV: true } },

      { id: 'linear_reg',       label: 'Linear Regression',               desc: 'Linear regression with R² and ANOVA table',           requires: { minContinuous: 2, minRows: 20, needsContinuousDV: true } },

      { id: 'linear_reg_2',     label: 'Linear Regression 2',             desc: 'Coefficient table with SE and 95% CI',                requires: { minContinuous: 2, minRows: 20 } },

      { id: 'linear_reg_3',     label: 'Linear Regression 3',             desc: 'Residuals and assumption diagnostic plots',           requires: { minContinuous: 2, minRows: 20 } },

      { id: 'multiple_linear',  label: 'Multiple Linear Regression',      desc: 'Multiple predictors → one continuous outcome',        requires: { minContinuous: 3, minRows: 30, needsContinuousDV: true } },

      { id: 'binary_logistic',  label: 'Binary Logistic Regression',      desc: 'Predict binary (yes/no) outcome',                     requires: { minContinuous: 1, minNominal: 1, minRows: 30, needsBinaryOutcome: true, needsNominalDV: true } },

      { id: 'multinomial_log',  label: 'Multinomial Logistic Regression', desc: 'Predict outcome with 3+ categories',                  requires: { minContinuous: 1, minNominal: 1, minRows: 50, needsNominalDV: true } },

      { id: 'ordinal_reg',      label: 'Proportional Odds Regression',    desc: 'Ordinal regression for ordered outcomes',             requires: { minContinuous: 1, minOrdinal: 1, minRows: 30, needsOrdinalDV: true } },

      { id: 'cox_regression',   label: 'Cox Regression',                  desc: 'Cox proportional hazards for survival analysis',      requires: { minContinuous: 2, minRows: 30 } },

      { id: 'poisson_regression',label: 'Poisson Regression',             desc: 'Predict count outcomes with Poisson GLM',             requires: { minContinuous: 1, minRows: 30, needsContinuousDV: true } },

      { id: 'neg_binomial',     label: 'Negative Binomial Regression',    desc: 'Count regression for overdispersed data',             requires: { minContinuous: 1, minRows: 30 } },

      { id: 'quantile_reg',     label: 'Quantile Regression',             desc: 'Median/conditional quantile regression',              requires: { minContinuous: 2, minRows: 30, needsContinuousDV: true } },

      { id: 'hierarchical',     label: 'Hierarchical Regression',         desc: 'Enter predictors in blocks to assess R² change',      requires: { minContinuous: 3, minRows: 40, needsContinuousDV: true } },

      { id: 'stepwise_reg',     label: 'Stepwise Regression',             desc: 'Automatic variable selection by significance',        requires: { minContinuous: 3, minRows: 40, needsContinuousDV: true } },

      { id: 'mediation',        label: 'Mediation Analysis',              desc: 'Test whether variable mediates IV → DV path',         requires: { minContinuous: 3, minRows: 50 } },

      { id: 'moderation',       label: 'Moderation / Interaction Analysis', desc: 'Test whether a variable moderates IV → DV effect',  requires: { minContinuous: 2, minRows: 50 } },

    ],

  },

  // ── Group 11: Reliability & Scale Analysis ────────────────────────────

  {

    id: 'reliability',

    label: 'Reliability & Scale Analysis',

    color: '#ef4444',

    icon: RiCheckboxCircleFill,

    desc: 'Assess instrument consistency and internal validity',

    techniques: [

      { id: 'cronbach_alpha',  label: "Cronbach's Alpha (α)",              desc: 'Internal consistency of a multi-item scale',          requires: { minOrdinal: 3 } },

      { id: 'mcdonald_omega',  label: "McDonald's Omega (ω)",              desc: "More robust alternative to Cronbach's alpha",         requires: { minOrdinal: 3 } },

      { id: 'kr20',            label: 'KR-20 (Kuder-Richardson)',          desc: 'Reliability for dichotomous items',                   requires: { minNominal: 3 } },

      { id: 'split_half',      label: 'Split-Half Reliability',            desc: 'Correlation between two halves of a test',            requires: { minOrdinal: 4 } },

      { id: 'icc',             label: 'Intraclass Correlation (ICC)',      desc: 'Agreement between raters or repeated measures',       requires: { minContinuous: 2 } },

      { id: 'item_analysis',   label: 'Item Analysis',                     desc: 'Item-total correlation and corrected item scores',    requires: { minOrdinal: 3 } },

    ],

  },

  // ── Group 12: Assumption Tests ────────────────────────────────────────

  {

    id: 'assumption',

    label: 'Assumption Tests',

    color: '#06b6d4',

    icon: RiMicroscopeFill,

    desc: 'Verify statistical assumptions before running tests',

    techniques: [

      { id: 'bartlett',        label: "Bartlett's Test",                   desc: 'Test equality of variances (sensitive to normality)', requires: { minContinuous: 1, groupCol: true } },

      { id: 'mauchly',         label: "Mauchly's Test of Sphericity",      desc: 'Assumption for repeated measures ANOVA',              requires: { minContinuous: 3 } },

      { id: 'durbin_watson',   label: 'Durbin-Watson Test',                desc: 'Autocorrelation in regression residuals',             requires: { minContinuous: 2 } },

      { id: 'vif',             label: 'Multicollinearity (VIF)',            desc: 'Variance inflation factor for regression predictors', requires: { minContinuous: 3 } },

    ],

  },

  // ── Group 13: Multivariate & Advanced ────────────────────────────────

  {

    id: 'multivariate',

    label: 'Multivariate & Advanced',

    color: '#6366f1',

    icon: RiBrainFill,

    desc: 'Advanced analyses for complex research designs',

    techniques: [

      { id: 'pca',             label: 'Principal Component Analysis (PCA)', desc: 'Reduce dimensionality of correlated variables',      requires: { minContinuous: 3, minRows: 50 } },

      { id: 'efa',             label: 'Exploratory Factor Analysis (EFA)',  desc: 'Discover underlying factor structure of items',      requires: { minOrdinal: 5, minRows: 50 } },

      { id: 'cfa',             label: 'Confirmatory Factor Analysis (CFA)', desc: 'Test a pre-specified factor structure',              requires: { minOrdinal: 5, minRows: 100 } },

      { id: 'discriminant',    label: 'Discriminant Analysis',              desc: 'Predict group membership from predictors',           requires: { minContinuous: 2, groupCol: true, minRows: 30 } },

      { id: 'cluster',         label: 'Cluster Analysis',                   desc: 'Group similar cases or variables together',          requires: { minContinuous: 2, minRows: 20 } },

      { id: 'sem',             label: 'Structural Equation Modelling (SEM)', desc: 'Test complex causal path models',                   requires: { minContinuous: 4, minRows: 100 } },

      { id: 'path_analysis',   label: 'Path Analysis',                      desc: 'Trace causal pathways between variables',            requires: { minContinuous: 3, minRows: 50 } },

      { id: 'survival',        label: 'Survival / Time-to-Event Analysis',  desc: 'Analyse time until an event occurs',                 requires: { minContinuous: 2, minRows: 30 } },

      { id: 'time_series',     label: 'Time Series Analysis',               desc: 'Patterns and trends in sequential data',             requires: { minContinuous: 1, minRows: 30 } },

    ],

  },

];









// ─── Wizard steps ─────────────────────────────────────────────────────

const STEPS = [

  { id: 1, label: 'Upload',     icon: RiDatabase2Fill,    desc: 'Upload data file' },

  { id: 2, label: 'Project',    icon: RiFocus2Fill,      desc: 'Topic & population' },

  { id: 3, label: 'Research',   icon: RiBrainFill,       desc: "RQs, hypotheses & objectives" },

  { id: 4, label: 'Variables',  icon: RiMicroscopeFill,  desc: "DV & IV driven by RQs" },

  { id: 5, label: 'Techniques', icon: RiCpuFill,         desc: 'Statistical methods' },

  { id: 6, label: 'Output',     icon: RiFileTextFill,    desc: 'Report format' },

];



// ─── Table catalogue ──────────────────────────────────────────────────

const TABLE_TYPES = [

  { id: 'descriptive',         label: 'Descriptive Statistics',   icon: RiBarChart2Fill,    color: '#6366f1', desc: 'Mean, SD, Min, Max, Median, Skewness, Kurtosis per variable' },

  { id: 'test_results',        label: 'Statistical Test Results', icon: RiFlaskFill,         color: '#10b981', desc: 'All tests: statistic, p-value, significance, effect size' },

  { id: 'frequency',           label: 'Frequency Tables',         icon: RiClipboardFill,     color: '#f59e0b', desc: 'Count & percentage for each categorical column' },

  { id: 'correlation',         label: 'Correlation Matrix Table', icon: RiStackFill,         color: '#ec4899', desc: 'Full Pearson r matrix as a numeric table' },

  { id: 'normality',           label: 'Normality Test Results',   icon: RiCheckboxCircleFill,color: '#3b82f6', desc: 'Pass/fail per variable across all normality tests' },

  { id: 'skewness_kurtosis',   label: 'Skewness & Kurtosis',      icon: RiPulseFill,         color: '#8b5cf6', desc: 'Skewness & kurtosis values with shape interpretation' },

  { id: 'outliers',            label: 'Outlier Detection',        icon: RiAlertFill,         color: '#ef4444', desc: 'IQR and z-score outlier counts with % of data affected' },

  { id: 'posthoc',             label: 'Post-hoc Comparisons',     icon: RiMicroscopeFill,    color: '#06b6d4', desc: 'Tukey HSD pairwise comparison with adjusted p-values' },

];



// ─── AvailableColumnsPanel ───────────────────────────────────────────────────
// Draggable column chips. Hover a chip → fixed viewport popup appears (via
// ReactDOM.createPortal so it NEVER clips into sidebars or overflow containers).

function AvailableColumnsPanel({
  dataDictionary,
  dvValue, ivValue, cvValue, mvValue, modvValue,
  covValue, exclValue, grpValue,
  onAddDv, onAddIv, onAddCv, onAddMv, onAddModv,
  onAddCov, onAddExcl, onAddGrp,
}: {
  dataDictionary: Record<string, any>;
  dvValue: string; ivValue: string; cvValue: string;
  mvValue: string; modvValue: string;
  covValue: string; exclValue: string; grpValue: string;
  onAddDv:   (col: string) => void;
  onAddIv:   (col: string) => void;
  onAddCv:   (col: string) => void;
  onAddMv:   (col: string) => void;
  onAddModv: (col: string) => void;
  onAddCov:  (col: string) => void;
  onAddExcl: (col: string) => void;
  onAddGrp:  (col: string) => void;
}) {
  const [hovered,  setHovered]  = React.useState<string | null>(null);
  const [popupPos, setPopupPos] = React.useState<{ top: number; left: number; openDown: boolean } | null>(null);
  const leaveTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => { setMounted(true); }, []);

  const POPUP_W = 520;
  const POPUP_H = 50;
  const GAP     = 8;

  const cancelLeave = () => { if (leaveTimer.current) clearTimeout(leaveTimer.current); };

  const startLeave = () => {
    leaveTimer.current = setTimeout(() => { setHovered(null); setPopupPos(null); }, 250);
  };

  const closePopup = () => { setHovered(null); setPopupPos(null); };

  const handleChipEnter = (col: string, e: React.MouseEvent<HTMLElement>) => {
    cancelLeave();
    const r  = e.currentTarget.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const openDown = r.top < POPUP_H + GAP + 20;
    let left = r.left + r.width / 2 - POPUP_W / 2;
    left = Math.max(8, Math.min(left, vw - POPUP_W - 8));
    const top = openDown ? r.bottom + GAP : r.top - POPUP_H - GAP;
    setPopupPos({ top, left, openDown });
    setHovered(col);
  };

  const toList = (v: string) => (v ? v.split(',').map(s => s.trim()).filter(Boolean) : []);
  const dvList   = toList(dvValue);
  const ivList   = toList(ivValue);
  const cvList   = toList(cvValue);
  const mvList   = toList(mvValue);
  const modvList = toList(modvValue);
  const covList  = toList(covValue);
  const exclList = toList(exclValue);
  const grpList  = toList(grpValue);

  const slotFor = (col: string) => {
    if (dvList.includes(col))   return 'DV';
    if (ivList.includes(col))   return 'IV';
    if (cvList.includes(col))   return 'CV';
    if (mvList.includes(col))   return 'MV';
    if (modvList.includes(col)) return 'MODV';
    if (covList.includes(col))  return 'COV';
    if (exclList.includes(col)) return 'EXCL';
    if (grpList.includes(col))  return 'GRP';
    return null;
  };

  const slotColor: Record<string, string> = {
    DV:   'var(--brand)',
    IV:   'var(--success)',
    CV:   '#f59e0b',
    MV:   '#8b5cf6',
    MODV: '#f97316',
    COV:  '#06b6d4',
    EXCL: '#ef4444',
    GRP:  '#84cc16',
  };

  const BTN_CFG = [
    { label: 'Dependent',   color: 'var(--brand)',   bg: 'rgba(99,102,241,0.13)',  hbg: 'rgba(99,102,241,0.28)',  bd: 'rgba(99,102,241,0.35)',  fn: onAddDv   },
    { label: 'Independent', color: 'var(--success)', bg: 'rgba(16,185,129,0.13)',  hbg: 'rgba(16,185,129,0.28)',  bd: 'rgba(16,185,129,0.35)',  fn: onAddIv   },
    { label: 'Control',     color: '#f59e0b',        bg: 'rgba(245,158,11,0.13)',  hbg: 'rgba(245,158,11,0.28)',  bd: 'rgba(245,158,11,0.35)',  fn: onAddCv   },
    { label: 'Mediator',    color: '#8b5cf6',        bg: 'rgba(139,92,246,0.13)',  hbg: 'rgba(139,92,246,0.28)',  bd: 'rgba(139,92,246,0.35)',  fn: onAddMv   },
    { label: 'Moderator',   color: '#f97316',        bg: 'rgba(249,115,22,0.13)',  hbg: 'rgba(249,115,22,0.28)',  bd: 'rgba(249,115,22,0.35)',  fn: onAddModv },
    { label: 'Covariate',   color: '#06b6d4',        bg: 'rgba(6,182,212,0.13)',   hbg: 'rgba(6,182,212,0.28)',   bd: 'rgba(6,182,212,0.35)',   fn: onAddCov  },
    { label: 'Exclude',     color: '#ef4444',        bg: 'rgba(239,68,68,0.13)',   hbg: 'rgba(239,68,68,0.28)',   bd: 'rgba(239,68,68,0.35)',   fn: onAddExcl },
    { label: 'Group',       color: '#84cc16',        bg: 'rgba(132,204,22,0.13)',  hbg: 'rgba(132,204,22,0.28)',  bd: 'rgba(132,204,22,0.35)',  fn: onAddGrp  },
  ];

  const slotBg: Record<string, string> = {
    DV:   'rgba(99,102,241,0.13)',
    IV:   'rgba(16,185,129,0.13)',
    CV:   'rgba(245,158,11,0.13)',
    MV:   'rgba(139,92,246,0.13)',
    MODV: 'rgba(249,115,22,0.13)',
    COV:  'rgba(6,182,212,0.13)',
    EXCL: 'rgba(239,68,68,0.13)',
    GRP:  'rgba(132,204,22,0.13)',
  };

  // Portal popup — rendered into document.body so no parent CSS can clip it
  const popup = (hovered && popupPos && mounted) ? ReactDOM.createPortal(
    <div
      onMouseEnter={cancelLeave}
      onMouseLeave={startLeave}
      style={{
        position: 'fixed',
        top: popupPos.top,
        left: popupPos.left,
        width: POPUP_W,
        zIndex: 2147483647,
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: '6px 6px',
        display: 'flex',
        gap: 4,
        flexWrap: 'wrap',
        boxShadow: '0 12px 40px rgba(0,0,0,0.55)',
        pointerEvents: 'auto',
      }}
    >
      {/* Caret toward chip */}
      <div style={{
        position: 'absolute', left: '50%', transform: 'translateX(-50%)',
        ...(popupPos.openDown
          ? { bottom: '100%', borderBottom: '6px solid var(--border)', borderTop: 'none' }
          : { top:    '100%', borderTop:    '6px solid var(--border)', borderBottom: 'none' }),
        width: 0, height: 0,
        borderLeft: '6px solid transparent', borderRight: '6px solid transparent',
      }} />
      <div style={{
        position: 'absolute', left: '50%', transform: 'translateX(-50%)',
        ...(popupPos.openDown
          ? { bottom: 'calc(100% - 1px)', borderBottom: '6px solid var(--surface)', borderTop: 'none' }
          : { top:    'calc(100% - 1px)', borderTop:    '6px solid var(--surface)', borderBottom: 'none' }),
        width: 0, height: 0,
        borderLeft: '6px solid transparent', borderRight: '6px solid transparent',
        zIndex: 1,
      }} />

      {BTN_CFG.map(btn => (
        <button
          key={btn.label}
          type="button"
          onClick={() => { if (hovered) { btn.fn(hovered); closePopup(); } }}
          style={{
            flex: '1 1 auto',
            fontSize: 10, fontWeight: 700, padding: '5px 8px', borderRadius: 7,
            cursor: 'pointer', whiteSpace: 'nowrap',
            background: btn.bg, color: btn.color,
            border: `1.5px solid ${btn.bd}`,
            transition: 'background 0.12s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = btn.hbg)}
          onMouseLeave={e => (e.currentTarget.style.background = btn.bg)}
        >
          {btn.label}
        </button>
      ))}
    </div>,
    document.body
  ) : null;

  return (
    <>
      <div style={{ marginTop: 8, border: '1px solid var(--border)', borderRadius: 12, background: 'var(--surface-2)' }}>
        <div style={{ padding: '8px 12px 6px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Available columns — drag to a field above, or hover to assign
          </span>
        </div>
        <div style={{ padding: '10px 12px 12px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {Object.entries(dataDictionary).map(([col, info]: [string, any]) => {
            const slot  = slotFor(col);
            const color = slot ? slotColor[slot] : 'var(--text-2)';
            const bg    = slot ? (slotBg[slot] || 'var(--surface)') : 'var(--surface)';
            const isHov = hovered === col;
            return (
              <span
                key={col}
                draggable
                onDragStart={e => { e.dataTransfer.setData('text/plain', col); e.dataTransfer.effectAllowed = 'copy'; }}
                onMouseEnter={e => handleChipEnter(col, e)}
                onMouseLeave={startLeave}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  padding: '5px 10px', borderRadius: 8, cursor: 'grab',
                  fontSize: 12, fontWeight: 600,
                  background: bg,
                  border: `1.5px solid ${slot ? color + '55' : 'var(--border)'}`,
                  color, userSelect: 'none',
                  transition: 'transform 0.1s, box-shadow 0.1s',
                  transform: isHov ? 'scale(1.04)' : 'scale(1)',
                  boxShadow: isHov ? `0 2px 12px ${color}44` : 'none',
                }}
                title={`${info?.level ? `Level: ${info.level} · ` : ''}Hover to assign role`}
              >
                <span style={{ fontSize: 9, opacity: 0.45 }}>⠿</span>
                {col}
                {slot && (
                  <span style={{
                    fontSize: 9, fontWeight: 800, padding: '1px 4px', borderRadius: 4,
                    background: color + '33', color, letterSpacing: '0.04em',
                  }}>{slot}</span>
                )}
              </span>
            );
          })}
        </div>
      </div>
      {popup}
    </>
  );
}

function MultiVarInput({ value, onChange, id, placeholder, accentColor = 'var(--brand)', errorBorder }: {

  value: string;

  onChange: (val: string) => void;

  id?: string;

  placeholder?: string;

  accentColor?: string;

  errorBorder?: boolean;

}) {

  const [inputText, setInputText] = React.useState('');

  const [isDragOver, setIsDragOver] = React.useState(false);

  const pills = value ? value.split(',').map(v => v.trim()).filter(Boolean) : [];



  const addPill = (raw: string) => {

    const parts = raw.split(',').map(v => v.trim()).filter(Boolean);

    if (!parts.length) return;

    const next = Array.from(new Set([...pills, ...parts]));

    onChange(next.join(', '));

    setInputText('');

  };



  const removePill = (idx: number) => {

    const next = pills.filter((_, i) => i !== idx);

    onChange(next.join(', '));

  };



  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {

    if (e.key === 'Enter' || e.key === ',') {

      e.preventDefault();

      addPill(inputText);

    } else if (e.key === 'Backspace' && !inputText && pills.length > 0) {

      removePill(pills.length - 1);

    }

  };



  const handleBlur = () => {

    if (inputText.trim()) addPill(inputText);

  };



  return (

    <div>

      <div

        id={id}

        className="input"

        style={{

          display: 'flex', flexWrap: 'wrap', gap: 6, minHeight: 42, height: 'auto',

          padding: '6px 10px', cursor: 'text', alignItems: 'center',

          borderColor: isDragOver ? accentColor : (errorBorder ? 'var(--danger)' : undefined),

          boxShadow: isDragOver ? `0 0 0 3px ${accentColor}33` : undefined,

          background: isDragOver ? `${accentColor}08` : undefined,

          transition: 'border-color 0.15s, box-shadow 0.15s, background 0.15s',

          position: 'relative',

        }}

        onClick={() => {

          const inp = document.getElementById((id || 'mvi') + '-input') as HTMLInputElement;

          inp?.focus();

        }}

        onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; setIsDragOver(true); }}

        onDragLeave={() => setIsDragOver(false)}

        onDrop={e => {

          e.preventDefault();

          setIsDragOver(false);

          const col = e.dataTransfer.getData('text/plain');

          if (col) addPill(col);

        }}

      >

        {/* Drop overlay label */}

        {isDragOver && (

          <div style={{

            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',

            justifyContent: 'center', borderRadius: 'inherit', pointerEvents: 'none',

            background: `${accentColor}10`,

          }}>

            <span style={{ fontSize: 12, fontWeight: 700, color: accentColor, opacity: 0.85 }}>

              Drop to add →

            </span>

          </div>

        )}

        {pills.map((pill, i) => (

          <span

            key={i}

            style={{

              display: 'inline-flex', alignItems: 'center', gap: 4,

              background: accentColor === 'var(--brand)' ? 'var(--border)'

                        : accentColor === 'var(--success)' ? 'rgba(16,185,129,0.15)'

                        : 'color-mix(in srgb, var(--warning) 15%, transparent)',

              color: accentColor, borderRadius: 6, padding: '2px 8px',

              fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', maxWidth: 200,

            }}

          >

            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 160 }}>{pill}</span>

            <button

              type="button"

              onClick={(e) => { e.stopPropagation(); removePill(i); }}

              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0, lineHeight: 1, fontSize: 14, opacity: 0.7 }}

            >×</button>

          </span>

        ))}

        <input

          id={(id || 'mvi') + '-input'}

          type="text"

          value={inputText}

          onChange={e => setInputText(e.target.value)}

          onKeyDown={handleKeyDown}

          onBlur={handleBlur}

          placeholder={placeholder || ''}

          style={{

            flex: 1, minWidth: 120, background: 'transparent', border: 'none',

            outline: 'none', fontSize: 13, color: 'var(--text)',

          }}

        />

      </div>

      {pills.length > 0 && (

        <p style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>

          {pills.length} variable{pills.length > 1 ? 's' : ''} · separate with comma or Enter

        </p>

      )}

    </div>

  );

}



// ─── Validation ───────────────────────────────────────────────────────

function validateStep(step: number, brief: any, dataFile: File | null = null, hasSurveyId: boolean = false): Record<string, string> {

  const errors: Record<string, string> = {};

  if (step === 1) {

    if (!dataFile && !hasSurveyId) errors.file = 'Please upload a data file to continue';

  }

  if (step === 2) {

    if (!brief.user_class)        errors.user_class = 'Please select who this analysis is for';

    if (!brief.research_design)   errors.research_design = 'Please select a research design';

    if (!brief.topic.trim())      errors.topic = 'Project topic is required';

    if (!brief.population.trim()) errors.population = 'Target population is required';

  }

  if (step === 3) {

    // Golden Rule: RQ/Hypotheses/Objectives come BEFORE variable selection

    if (!brief.objectives[0].trim())  errors.objectives = 'At least one objective is required';

    if (!brief.research_questions[0].trim()) errors.research_questions = 'At least one research question is required';

    if (!brief.hypotheses[0].trim())  errors.hypotheses = 'At least one hypothesis is required';

  }

  if (step === 4) {

    // Variables are chosen AFTER RQs are defined — RQs drive variable selection

    if (!brief.dependent_variable.trim())   errors.dependent_variable = 'Add at least one dependent variable';

    if (!brief.independent_variable.trim()) errors.independent_variable = 'Add at least one independent variable';

  }

  return errors;

}



// ─── Step progress bar (redesigned) ────────────────────────────────────

function StepBar({ current, onGoto }: { current: number; onGoto: (n: number) => void }) {

  return (

    <div style={{ display: 'flex', alignItems: 'center', gap: 0, padding: '0 4px', marginBottom: 20 }}>

      {STEPS.map((step, idx) => {

        const Icon = step.icon;

        const done   = current > step.id;

        const active = current === step.id;

        return (

          <React.Fragment key={step.id}>

            <button

              onClick={() => done && onGoto(step.id)}

              style={{

                cursor: done ? 'pointer' : 'default',

                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,

                background: 'none', border: 'none', padding: '0 2px', minWidth: 60,

              }}

              title={done ? `Go back to ${step.label}` : step.label}

            >

              <div style={{

                width: 38, height: 38, borderRadius: '50%',

                display: 'flex', alignItems: 'center', justifyContent: 'center',

                background: done

                  ? 'linear-gradient(135deg,#10b981,#059669)'

                  : active

                  ? 'linear-gradient(135deg,#6366f1,#4f46e5)'

                  : 'var(--surface-2)',

                border: active

                  ? '2px solid rgba(99,102,241,0.5)'

                  : done ? '2px solid rgba(16,185,129,0.4)'

                  : '2px solid var(--border)',

                boxShadow: active

                  ? '0 0 0 5px color-mix(in srgb, var(--brand) 10%, transparent),0 4px 12px rgba(99,102,241,0.25)'

                  : done ? '0 2px 8px rgba(16,185,129,0.2)' : 'none',

                color: done || active ? '#fff' : 'var(--text-3)',

                transition: 'all 0.35s cubic-bezier(0.34,1.56,0.64,1)',

                transform: active ? 'scale(1.08)' : 'scale(1)',

              }}>

                {done ? <RiCheckboxCircleFill size={17} /> : <Icon size={15} />}

              </div>

              <p style={{

                fontSize: 10, fontWeight: active ? 700 : done ? 600 : 500, margin: 0,

                color: active ? 'var(--brand)' : done ? 'var(--success)' : 'var(--text-3)',

                lineHeight: 1, whiteSpace: 'nowrap', transition: 'color 0.2s',

              }}>

                {step.label}

              </p>

            </button>

            {idx < STEPS.length - 1 && (

              <div style={{

                flex: 1, height: 2, marginBottom: 18, borderRadius: 2, minWidth: 8,

                background: done

                  ? 'linear-gradient(90deg,#10b981,#059669)'

                  : active

                  ? 'linear-gradient(90deg,#6366f1 0%,var(--border) 100%)'

                  : 'var(--border)',

                transition: 'background 0.4s ease',

              }} />

            )}

          </React.Fragment>

        );

      })}

    </div>

  );

}





// ─── Field wrapper ────────────────────────────────────────────────────

function Field({ label, error, required = true, hint, children }: {

  label: string; error?: string; required?: boolean; hint?: string; children: React.ReactNode;

}) {

  return (

    <div className="space-y-1.5">

      <label className="flex items-center gap-1" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)' }}>

        {label}

        {required && <span style={{ color: 'var(--danger)', fontSize: 11 }}>*</span>}

      </label>

      {children}

      {hint && !error && <p className="text-xs" style={{ color: 'var(--text-3)' }}>{hint}</p>}

      {error && (

        <p className="text-xs flex items-center gap-1" style={{ color: 'var(--danger)' }}>

          <RiErrorWarningFill size={11} /> {error}

        </p>

      )}

    </div>

  );

}



// ─── File Drop Zone ───────────────────────────────────────────────────

function FileDropZone({ onUpload }: { onUpload: (f: File) => void }) {

  const [sourceType, setSourceType] = useState<'file' | 'sheets'>('file');

  const [sheetUrl, setSheetUrl] = useState('');

  const [importing, setImporting] = useState(false);



  const onDrop = useCallback((files: File[]) => { if (files[0]) onUpload(files[0]); }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({

    onDrop,

    accept: {

      'application/vnd.ms-excel': ['.xls'],

      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],

      'text/csv': ['.csv'],

      'application/octet-stream': ['.sav'],

    },

    maxFiles: 1,

  });

  const handleImportSheet = async () => {

    if (!sheetUrl) return toast.error('Please enter a Google Sheets URL');

    setImporting(true);

    toast.loading("Importing from Google Sheets...", { id: "import" });

    try {

      const importRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/integrations/google/import-sheets`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json',

          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`

        },

        body: JSON.stringify({ spreadsheet_url: sheetUrl })

      });

      if (!importRes.ok) {

        toast.dismiss("import");

        const errData = await importRes.json();

        return toast.error(errData.detail || 'Failed to import Google Sheet');

      }

      const importData = await importRes.json();

      toast.dismiss("import");

      toast.success(`Imported ${importData.rows_imported} rows`);

      

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/storage/dataframes/${importData.filename}`);

      const blob = await response.blob();

      const finalFile = new (window as any).File([blob], importData.filename, { type: 'text/csv' });

      onUpload(finalFile);

    } catch (e) {

      toast.dismiss("import");

      toast.error('Failed to import Google Sheet');

    } finally {

      setImporting(false);

    }

  };



  return (

    <div className="rounded-2xl border-2 cursor-pointer transition-all duration-200"

      style={{

        borderColor: isDragActive ? 'var(--brand)' : 'var(--border)',

        background: isDragActive ? 'rgba(99,102,241,0.06)' : 'var(--surface-2)',

        overflow: 'hidden'

      }}

    >

      <div className="flex bg-[var(--surface)] border-b border-[var(--border)]">

        <button type="button" onClick={() => setSourceType('file')} className={`flex-1 py-3 text-sm font-semibold transition-all ${sourceType === 'file' ? 'text-[var(--brand)] border-b-2 border-[var(--brand)]' : 'text-[var(--text-3)] hover:bg-[var(--surface-2)]'}`}>File Upload</button>

        <button type="button" onClick={() => setSourceType('sheets')} className={`flex-1 py-3 text-sm font-semibold transition-all ${sourceType === 'sheets' ? 'text-[#22c55e] border-b-2 border-[#22c55e]' : 'text-[var(--text-3)] hover:bg-[var(--surface-2)]'}`}>Google Sheets</button>

      </div>



      {sourceType === 'file' ? (

        <div {...getRootProps()} style={{ padding: '40px 24px', textAlign: 'center' }}>

          <input {...getInputProps()} />

          <div

            className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 transition-all duration-200"

            style={{

              background: isDragActive ? 'var(--border)' : 'rgba(99,102,241,0.08)',

              border: `1.5px solid ${isDragActive ? 'rgba(99,102,241,0.4)' : 'var(--border)'}`,

            }}

          >

            <RiFileUploadFill size={28} style={{ color: isDragActive ? 'var(--brand)' : '#818cf8' }} />

          </div>

          <p className="font-bold text-base mb-1" style={{ color: 'var(--text)', fontFamily: 'Syne, sans-serif' }}>

            {isDragActive ? 'Release to upload' : 'Drop your data file here'}

          </p>

          <p className="text-sm mb-4" style={{ color: 'var(--text-2)' }}>

            or <span style={{ color: 'var(--brand)', fontWeight: 600 }}>click to browse</span>

          </p>

          <div className="flex justify-center gap-2 flex-wrap">

            {['.xlsx', '.xls', '.csv', '.sav'].map(ext => (

              <span key={ext} className="px-2.5 py-1 rounded-lg text-xs font-semibold font-mono"

                style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-3)' }}>

                {ext}

              </span>

            ))}

          </div>

        </div>

      ) : (

        <div style={{ padding: '40px 24px', textAlign: 'center' }}>

          <div

            className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 transition-all duration-200"

            style={{

              background: 'rgba(34,197,94,0.08)',

              border: '1.5px solid rgba(34,197,94,0.15)',

            }}

          >

            <RiDatabase2Fill size={28} style={{ color: '#4ade80' }} />

          </div>

          <p className="font-bold text-base mb-2" style={{ color: 'var(--text)', fontFamily: 'Syne, sans-serif' }}>

            Import from Google Sheets

          </p>

          <p className="text-sm mb-5 text-[var(--text-2)] max-w-md mx-auto">

            Make sure your Google account is connected in <a href="/settings/integrations" target="_blank" className="text-[#22c55e] hover:underline">Integrations</a> and the sheet is accessible.

          </p>

          <div className="max-w-md mx-auto flex gap-2">

            <input 

              type="url" 

              placeholder="https://docs.google.com/spreadsheets/d/..." 

              className="input flex-1" 

              value={sheetUrl} 

              onChange={e => setSheetUrl(e.target.value)} 

              onClick={(e) => e.stopPropagation()}

            />

            <button 

              className="btn btn-primary" 

              style={{ background: '#22c55e', borderColor: '#22c55e' }}

              onClick={(e) => { e.stopPropagation(); handleImportSheet(); }}

              disabled={importing || !sheetUrl}

            >

              {importing ? <RiLoader4Line size={16} className="animate-spin" /> : 'Import'}

            </button>

          </div>

        </div>

      )}

    </div>

  );

}



// ─── Report type config ───────────────────────────────────────────────

const REPORT_TYPES = [

  { value: 'chapter4',         label: 'Dissertation Chapter',  sub: 'University Chapter 4',      icon: RiGraduationCapFill, color: '#6366f1' },

  { value: 'business_report',  label: 'Business Report',       sub: 'Corporate / professional',  icon: RiBarChart2Fill,     color: '#10b981' },

  { value: 'executive_summary',label: 'Executive Summary',     sub: 'Board / C-suite brief',     icon: RiFlashlightFill,    color: '#f59e0b' },

  { value: 'technical_report', label: 'Technical Report',      sub: 'Science / engineering',     icon: RiFlaskFill,         color: '#ef4444' },

  { value: 'slide_deck',       label: 'Slide Deck Briefing',   sub: 'Presentations',             icon: RiProjectorFill,     color: '#ec4899' },

  { value: 'research_paper',   label: 'Research Paper',        sub: 'Journal / APA format',      icon: RiFileTextFill,      color: '#3b82f6' },

  { value: 'academic_report',  label: 'Academic Report',       sub: 'Project / thesis report',   icon: RiClipboardFill,     color: '#8b5cf6' },

];



// ─── Compatibility checker ─────────────────────────────────────────────────

// Requirement fields supported in technique `requires` objects:

//   minContinuous   – min continuous columns

//   minOrdinal      – min ordinal-or-above columns (ordinal + continuous)

//   minNominal      – min nominal/categorical columns

//   minRows         – min row count

//   groupCol        – needs a grouping column (2–20 groups)

//   minGroups       – grouping col must have ≥ N distinct groups

//   maxGroups       – grouping col must have ≤ N distinct groups (e.g. T-test: 2)

//   exactGroups     – grouping col must have exactly N groups

//   minCols         – min total columns (any type)

//   needsBinaryOutcome  – DV should be binary (0/1, yes/no)

//   needsContinuousDV   – DV must be continuous (regression, ANOVA)

//   needsOrdinalDV      – DV must be ordinal/scale (ordinal regression)

//   needsNominalDV      – DV must be categorical (logistic regression)

//   needsPaired     – needs exactly 2 related continuous measures

//   minRepeated     – needs N repeated-measure continuous columns

//   qualOnly        – only appropriate for qualitative studies

//   quantOnly       – only appropriate for quantitative studies

type DataDictionary = Record<string, { dtype: string; level: string; n_unique: number; n_missing: number; n_rows: number }>;



function checkCompatibility(

  requires: Record<string, any>,

  dataDictionary: DataDictionary | null,

  brief?: any

): { compatible: boolean; reasons: string[] } {

  if (!dataDictionary) return { compatible: true, reasons: [] };

  const rawCols = Object.entries(dataDictionary);

  if (rawCols.length === 0) return { compatible: true, reasons: [] };



  // ── 1. Normalise all columns to a unified level ──────────────────────────

  // Three data sources, each using different field name / values:

  //   File upload:  { level: "continuous"|"ordinal"|"nominal" }

  //   Survey path:  { level: already normalised by survey dict builder }

  //   Legacy raw:   { type: "ratio"|"interval"|"ordinal"|"nominal" }

  function normaliseLevel(col: any): 'continuous' | 'ordinal' | 'nominal' {

    const raw = (col.level || col.type || '').toLowerCase();

    if (raw === 'ratio' || raw === 'interval' || raw === 'continuous') return 'continuous';

    if (raw === 'ordinal') return 'ordinal';

    if (raw === 'nominal') return 'nominal';

    // dtype fallback

    const dtype = (col.dtype || '').toLowerCase();

    if (dtype.includes('float') || dtype.includes('double')) return 'continuous';

    if (dtype.includes('int')) return (col.n_unique ?? 0) > 10 ? 'continuous' : 'ordinal';

    return 'nominal';

  }



  const cols    = rawCols.map(([name, c]) => ({ name, ...c, _lvl: normaliseLevel(c) }));

  const nRows   = cols[0]?.n_rows ?? 0;



  // ── 2. Column counts ─────────────────────────────────────────────────────

  const nContinuous  = cols.filter(c => c._lvl === 'continuous').length;

  const nOrdinalPlus = cols.filter(c => c._lvl === 'continuous' || c._lvl === 'ordinal').length;

  const nNominal     = cols.filter(c => c._lvl === 'nominal').length;

  const nTotal       = cols.length;



  // ── 3. Group column detection ────────────────────────────────────────────

  // Accept nominal (2–20 groups) OR ordinal with few values (coded groups like 1/2/3)

  const groupCols = cols.filter(c => {

    const nu = c.n_unique ?? 0;

    if (c._lvl === 'nominal'  && nu >= 2 && nu <= 20) return true;

    if (c._lvl === 'ordinal'  && nu >= 2 && nu <= 10) return true;

    return false;

  });

  const hasGroupCol   = groupCols.length > 0;

  const maxGroupCount = hasGroupCol ? Math.max(...groupCols.map(c => c.n_unique ?? 0)) : 0;

  const minGroupCount = hasGroupCol ? Math.min(...groupCols.map(c => c.n_unique ?? 0)) : 0;



  // ── 4. Brief-derived signals ─────────────────────────────────────────────

  const dvName       = (brief?.dependent_variable  || '').trim().toLowerCase();

  const ivName       = (brief?.independent_variable || '').trim().toLowerCase();

  const studyType    = (brief?.study_type || 'quantitative').toLowerCase();

  const isQual       = studyType.includes('qual');

  const isQuant      = !isQual;



  // Try to find the DV column in the dictionary (fuzzy name match)

  const dvCol = dvName

    ? cols.find(c => c.name.toLowerCase().includes(dvName) || dvName.includes(c.name.toLowerCase()))

    : null;

  const dvLevel = dvCol ? dvCol._lvl : null;

  const dvUnique = dvCol ? (dvCol.n_unique ?? 0) : 0;



  // ── 5. Evaluate all conditions ───────────────────────────────────────────

  const reasons: string[] = [];



  if (requires.quantOnly && isQual) {

    reasons.push('This test requires quantitative data — your study is qualitative');

  }

  if (requires.qualOnly && isQuant) {

    reasons.push('This analysis is for qualitative studies — consider thematic analysis instead');

  }

  if (requires.minContinuous && nContinuous < requires.minContinuous) {

    reasons.push(`Needs ≥${requires.minContinuous} continuous variable${requires.minContinuous > 1 ? 's' : ''} — dataset has ${nContinuous}`);

  }

  if (requires.minOrdinal && nOrdinalPlus < requires.minOrdinal) {

    reasons.push(`Needs ≥${requires.minOrdinal} ordinal/scale variable${requires.minOrdinal > 1 ? 's' : ''} — dataset has ${nOrdinalPlus}`);

  }

  if (requires.minNominal && nNominal < requires.minNominal) {

    reasons.push(`Needs ≥${requires.minNominal} categorical variable${requires.minNominal > 1 ? 's' : ''} — dataset has ${nNominal}`);

  }

  if (requires.minCols && nTotal < requires.minCols) {

    reasons.push(`Needs ≥${requires.minCols} total columns — dataset has ${nTotal}`);

  }

  if (requires.minRows && nRows > 0 && nRows < requires.minRows) {

    reasons.push(`Needs ≥${requires.minRows} rows for stable results — dataset has ${nRows}`);

  }

  if (requires.groupCol && !hasGroupCol) {

    reasons.push('Needs a grouping column with 2–20 distinct categories');

  }

  if (requires.minGroups && hasGroupCol && minGroupCount < requires.minGroups) {

    reasons.push(`Needs a group variable with ≥${requires.minGroups} groups — found ${minGroupCount}`);

  }

  if (requires.maxGroups && hasGroupCol && maxGroupCount > requires.maxGroups) {

    reasons.push(`Designed for ≤${requires.maxGroups} groups — dataset has up to ${maxGroupCount} (consider ANOVA instead)`);

  }

  if (requires.exactGroups && hasGroupCol && !groupCols.some(c => c.n_unique === requires.exactGroups)) {

    reasons.push(`Requires exactly ${requires.exactGroups} groups — check your grouping variable`);

  }



  // DV-level checks (only when DV is specified in brief and found in dataset)

  if (dvCol) {

    if (requires.needsContinuousDV && dvLevel !== 'continuous') {

      reasons.push(`DV "${dvCol.name}" appears ${dvLevel} — this test needs a continuous outcome`);

    }

    if (requires.needsOrdinalDV && dvLevel === 'nominal') {

      reasons.push(`DV "${dvCol.name}" appears nominal — this test needs an ordinal/scale outcome`);

    }

    if (requires.needsNominalDV && dvLevel === 'continuous') {

      reasons.push(`DV "${dvCol.name}" appears continuous — this test predicts categorical outcomes`);

    }

    if (requires.needsBinaryOutcome && dvUnique !== 2) {

      reasons.push(`DV "${dvCol.name}" has ${dvUnique} values — binary logistic regression needs exactly 2 (e.g. 0/1)`);

    }

  } else if (dvName) {

    // DV named but not found — can still do generic DV-level checks

    if (requires.needsContinuousDV && nContinuous === 0) {

      reasons.push(`No continuous variable found to serve as the DV ("${dvName}")`);

    }

    if (requires.needsBinaryOutcome && !cols.some(c => c.n_unique === 2)) {

      reasons.push('Binary logistic regression needs a variable with exactly 2 outcome values');

    }

  }



  // Paired/repeated measures

  if (requires.needsPaired && nContinuous < 2) {

    reasons.push(`Needs ≥2 related continuous measures (pre/post) — dataset has ${nContinuous}`);

  }

  if (requires.minRepeated && nContinuous < requires.minRepeated) {

    reasons.push(`Repeated measures needs ≥${requires.minRepeated} time-point columns — dataset has ${nContinuous}`);

  }



  return { compatible: reasons.length === 0, reasons };

}





// ─── AI Reasoning Panel (Auto-Select) ────────────────────────────────

function AutoSelectReasoningPanel({ brief, dataDictionary, studyTypes }: {

  brief: any;

  dataDictionary: any;

  studyTypes: string[];

}) {

  // ── Derive signals from brief + dataDictionary ──

  const topic        = brief?.topic?.trim() || '';

  const objectives   = (brief?.objectives || []).filter(Boolean);

  const hypotheses   = (brief?.hypotheses || []).filter(Boolean);

  const dv           = brief?.dependent_variable?.trim() || '';

  const iv           = brief?.independent_variable?.trim() || '';

  const cv           = brief?.control_variable?.trim() || '';

  const nv           = brief?.nesting_variable?.trim() || '';

  const population   = brief?.population?.trim() || '';

  const sigLevel     = brief?.significance_level || 0.05;

  const studyType    = brief?.study_type || 'quantitative';



  // dataDictionary is a per-column Record: { colName: { level, dtype, n_unique, n_missing, n_rows } }

  // Derive all variable lists from it

  const colEntries = dataDictionary ? Object.entries(dataDictionary as Record<string, any>) : [];

  const nominalVars    = colEntries.filter(([, v]) => v.level === 'nominal').map(([k]) => k);

  const ordinalVars    = colEntries.filter(([, v]) => v.level === 'ordinal').map(([k]) => k);

  const continuousVars = colEntries.filter(([, v]) => v.level === 'continuous').map(([k]) => k);

  const nRows  = colEntries.length > 0 ? (colEntries[0][1]?.n_rows ?? 0) : 0;

  const nCols  = colEntries.length;



  const hasData    = colEntries.length > 0;

  const hasDV      = !!dv;

  const hasIV      = !!iv;

  const hasCV      = !!cv;

  // Find n_unique for first nominal var (group column estimate)

  const firstNominal = colEntries.find(([, v]) => v.level === 'nominal');

  const nGroups    = firstNominal ? (firstNominal[1]?.n_unique ?? 0) : 0;

  const hasLikert  = ordinalVars.length > 0;

  const isLargeN   = nRows >= 50;

  const isSmallN   = nRows > 0 && nRows < 30;

  const hasGroups  = nominalVars.length > 0;

  const isExperimental = studyTypes.includes('experimental');

  const isQual         = studyTypes.includes('qualitative') || studyTypes.includes('mixed');

  const isCorrelation  = studyTypes.includes('correlation');

  const isDescriptive  = studyTypes.includes('descriptive');

  const isMixed        = studyTypes.includes('mixed');



  // Derive predicted test families

  type Signal = { label: string; value: string; color: string; tier: string };

  const signals: Signal[] = [];



  // — Topic signal

  if (topic) signals.push({ label: 'Research Topic', value: topic.length > 55 ? topic.slice(0,55)+'…' : topic, color: '#6366f1', tier: 'context' });

  // — Study design

  signals.push({ label: 'Study Design', value: studyTypes.map((s: string) => s.replace(/_/g,' ')).join(', '), color: '#8b5cf6', tier: 'context' });

  // — Population

  if (population) signals.push({ label: 'Population / Sample', value: population.length > 55 ? population.slice(0,55)+'…' : population, color: '#06b6d4', tier: 'context' });

  // — Objectives

  if (objectives.length > 0) signals.push({ label: `${objectives.length} Research Objective${objectives.length > 1 ? 's' : ''}`, value: objectives.length === 1 ? (objectives[0].length > 60 ? objectives[0].slice(0,60)+'…' : objectives[0]) : `${objectives.slice(0,2).map((o: string) => o.slice(0,35)+'…').join(' • ')}`, color: '#f59e0b', tier: 'context' });

  // — Hypotheses

  if (hypotheses.length > 0) signals.push({ label: `${hypotheses.length} Hypothesis/Hypotheses`, value: `Each will be addressed by ≥1 inferential test`, color: '#ec4899', tier: 'context' });

  // — Variables

  if (hasDV) signals.push({ label: 'Dependent Variable', value: dv.length > 55 ? dv.slice(0,55)+'…' : dv, color: '#ef4444', tier: 'dataset' });

  if (hasIV) signals.push({ label: 'Independent Variable(s)', value: iv.length > 55 ? iv.slice(0,55)+'…' : iv, color: '#f97316', tier: 'dataset' });

  if (hasCV) signals.push({ label: 'Control Variable(s)', value: cv.length > 55 ? cv.slice(0,55)+'…' : cv, color: '#64748b', tier: 'dataset' });

  // — Dataset composition

  if (hasData) {

    signals.push({ label: 'Dataset Size', value: `${nRows.toLocaleString()} rows × ${nCols} columns — ${isLargeN ? 'Large sample (n≥50)' : isSmallN ? 'Small sample (n<30)' : 'Medium sample'}`, color: '#10b981', tier: 'dataset' });

    if (continuousVars.length > 0) signals.push({ label: 'Continuous Variables', value: `${continuousVars.length} variable${continuousVars.length>1?'s':''} (${continuousVars.slice(0,3).join(', ')}${continuousVars.length>3?' …':''})`, color: '#3b82f6', tier: 'dataset' });

    if (ordinalVars.length > 0)    signals.push({ label: 'Ordinal / Likert Variables', value: `${ordinalVars.length} variable${ordinalVars.length>1?'s':''} → Cronbach α + non-parametric tests`, color: '#8b5cf6', tier: 'dataset' });

    if (nominalVars.length > 0)    signals.push({ label: 'Categorical Variables', value: `${nominalVars.length} variable${nominalVars.length>1?'s':''} → Chi-square / frequency analysis`, color: '#06b6d4', tier: 'dataset' });

  }



  // — Predicted test families

  type Prediction = { label: string; why: string; color: string };

  const predictions: Prediction[] = [];

  predictions.push({ label: 'Descriptive Statistics', why: 'Always included as mandatory baseline', color: '#6366f1' });

  predictions.push({ label: 'Normality Testing', why: hasData ? `Required before choosing parametric vs non-parametric (n=${nRows})` : 'Required for all continuous variables', color: '#8b5cf6' });

  if (nominalVars.length > 0) predictions.push({ label: 'Frequency Analysis', why: `${nominalVars.length} categorical variable${nominalVars.length>1?'s':''} detected`, color: '#06b6d4' });

  if (hasLikert) predictions.push({ label: "Cronbach's Alpha", why: `${ordinalVars.length} Likert/ordinal variable${ordinalVars.length>1?'s':''} → reliability check`, color: '#f59e0b' });

  if (hasDV && hasIV && (isCorrelation || studyType === 'correlation')) predictions.push({ label: 'Correlation Analysis', why: 'Correlation study type + DV/IV defined', color: '#ec4899' });

  if (hasDV && hasIV && continuousVars.length >= 2) predictions.push({ label: 'Regression Analysis', why: `DV + ${iv.includes(',') ? 'multiple IVs' : 'IV'} detected → simple/multiple regression`, color: '#3b82f6' });

  if (hasGroups && hasDV && nGroups >= 3) predictions.push({ label: 'ANOVA / Kruskal-Wallis', why: `${nGroups} groups in categorical variable + continuous DV`, color: '#10b981' });

  if (hasGroups && hasDV && nGroups === 2) predictions.push({ label: 'T-test / Mann-Whitney', why: `2-group comparison + continuous DV`, color: '#f97316' });

  if (isExperimental) predictions.push({ label: 'Experimental Tests', why: 'Experimental design → paired t-test / repeated ANOVA', color: '#ef4444' });

  if (hasCV) predictions.push({ label: 'ANCOVA / Partial Correlation', why: 'Control variable(s) detected → covariate-adjusted tests', color: '#64748b' });

  if (hypotheses.length > 1) predictions.push({ label: 'Multiple Inferential Tests', why: `${hypotheses.length} hypotheses → each receives dedicated test + effect size`, color: '#ec4899' });

  if (isQual || isMixed) predictions.push({ label: 'Qualitative / Thematic Analysis', why: 'Qualitative or mixed-method study type selected', color: '#f59e0b' });

  if (isDescriptive) predictions.push({ label: 'Descriptive Analysis', why: 'Descriptive study type → comprehensive descriptive tests', color: '#10b981' });



  const contextSignals = signals.filter(s => s.tier === 'context');

  const datasetSignals = signals.filter(s => s.tier === 'dataset');



  const hasAnyContext = contextSignals.length > 0 || datasetSignals.length > 0;



  return (

    <div className="space-y-4 animate-slide-up">

      {/* Header */}

      <div className="rounded-xl p-4" style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.08), rgba(139,92,246,0.06))', border: '1.5px solid rgba(99,102,241,0.2)' }}>

        <div className="flex items-center gap-3 mb-3">

          <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)' }}>

            <RiSparklingFill size={18} color="#fff" />

          </div>

          <div>

            <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', margin: 0 }}>AI Statistical Intelligence</p>

            <p style={{ fontSize: 11, color: 'var(--text-3)', margin: 0 }}>Analysing your study context to choose the optimal test suite</p>

          </div>

        </div>



        {/* Completeness bar */}

        {(() => {

          const total = 6;

          const filled = [topic, objectives.length > 0, hypotheses.length > 0, hasDV, hasIV, hasData].filter(Boolean).length;

          const pct = Math.round((filled / total) * 100);

          const color = pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';

          return (

            <div>

              <div className="flex items-center justify-between mb-1">

                <span style={{ fontSize: 10, color: 'var(--text-3)', fontWeight: 600 }}>CONTEXT COMPLETENESS</span>

                <span style={{ fontSize: 10, color, fontWeight: 700 }}>{pct}% — {pct >= 80 ? 'Excellent' : pct >= 50 ? 'Good' : 'Add more details for better selection'}</span>

              </div>

              <div className="rounded-full overflow-hidden" style={{ height: 5, background: 'var(--surface)' }}>

                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${color}, ${color}aa)` }} />

              </div>

            </div>

          );

        })()}

      </div>



      {/* Research Context Signals */}

      {contextSignals.length > 0 && (

        <div>

          <p className="text-xs font-bold mb-2" style={{ color: 'var(--text-3)', letterSpacing: '0.06em' }}>RESEARCH CONTEXT</p>

          <div className="space-y-2">

            {contextSignals.map((s, i) => (

              <div key={i} className="flex items-start gap-2.5 rounded-lg px-3 py-2.5" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>

                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: s.color, marginTop: 5 }} />

                <div className="flex-1 min-w-0">

                  <p style={{ fontSize: 10, fontWeight: 700, color: s.color, margin: '0 0 1px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</p>

                  <p style={{ fontSize: 12, color: 'var(--text-2)', margin: 0, lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.value}</p>

                </div>

                <RiCheckboxCircleFill size={13} style={{ color: s.color, flexShrink: 0, marginTop: 3 }} />

              </div>

            ))}

          </div>

        </div>

      )}



      {/* Dataset Signals */}

      {datasetSignals.length > 0 && (

        <div>

          <p className="text-xs font-bold mb-2" style={{ color: 'var(--text-3)', letterSpacing: '0.06em' }}>DATASET PROFILE</p>

          <div className="space-y-2">

            {datasetSignals.map((s, i) => (

              <div key={i} className="flex items-start gap-2.5 rounded-lg px-3 py-2.5" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>

                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: s.color, marginTop: 5 }} />

                <div className="flex-1 min-w-0">

                  <p style={{ fontSize: 10, fontWeight: 700, color: s.color, margin: '0 0 1px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</p>

                  <p style={{ fontSize: 12, color: 'var(--text-2)', margin: 0, lineHeight: 1.4 }}>{s.value}</p>

                </div>

                <RiCheckboxCircleFill size={13} style={{ color: s.color, flexShrink: 0, marginTop: 3 }} />

              </div>

            ))}

          </div>

        </div>

      )}



      {/* No context fallback */}

      {!hasAnyContext && (

        <div className="rounded-xl p-4 text-center" style={{ background: 'var(--surface-2)', border: '1px dashed rgba(245,158,11,0.3)' }}>

          <RiAlertFill size={18} style={{ color: 'var(--warning)', margin: '0 auto 6px' }} />

          <p style={{ fontSize: 12, color: 'var(--text-2)', margin: 0 }}>Complete your research brief (Steps 1–3) for more accurate AI test selection</p>

        </div>

      )}



      {/* Predicted Test Families */}

      <div>

        <p className="text-xs font-bold mb-2" style={{ color: 'var(--text-3)', letterSpacing: '0.06em' }}>PREDICTED TEST SUITE ({predictions.length} categories)</p>

        <div className="grid grid-cols-1 gap-1.5">

          {predictions.map((p, i) => (

            <div key={i} className="flex items-center gap-2.5 rounded-lg px-3 py-2" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>

              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color }} />

              <div className="flex-1 min-w-0">

                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', margin: 0 }}>{p.label}</p>

                <p style={{ fontSize: 11, color: 'var(--text-3)', margin: 0, lineHeight: 1.3 }}>{p.why}</p>

              </div>

              <div className="w-1.5 h-1.5 rounded-full flex-shrink-0 opacity-50" style={{ background: p.color }} />

            </div>

          ))}

        </div>

      </div>



      {/* 5-Tier Framework Summary */}

      <div className="rounded-xl p-4 space-y-2.5" style={{ background: 'rgba(99,102,241,0.04)', border: '1px solid color-mix(in srgb, var(--brand) 10%, transparent)' }}>

        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand)', margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>5-Tier AI Selection Framework</p>

        {[

          { n: '1', label: 'Mandatory Baseline', desc: 'Descriptive stats, frequency tables, normality tests for all variables' },

          { n: '2', label: 'Assumption Checks', desc: "Levene's, VIF, Mauchly's, Bartlett's — chosen based on Tier 3 tests" },

          { n: '3', label: 'Primary Inferential Tests', desc: `Driven by: ${[hasDV && hasIV ? 'DV/IV relationship' : '', hasGroups ? `${nGroups || '?'} groups detected` : '', hasLikert ? 'Likert items present' : '', `n=${nRows || '?'}`, hypotheses.length > 0 ? `${hypotheses.length} hypothesis/hypotheses` : ''].filter(Boolean).join(' · ') || 'study design & objectives'}` },

          { n: '4', label: 'Effect Sizes & Post-Hoc', desc: "Every inferential test paired with Cohen's d / η² / r and post-hoc corrections" },

          { n: '5', label: 'Advanced Methods', desc: `${[cv ? 'ANCOVA (covariate)' : '', isQual ? 'Qualitative thematic analysis' : '', objectives.length > 2 ? 'Multi-objective test coverage' : ''].filter(Boolean).join(', ') || 'Applied if data profile supports them'}` },

        ].map(s => (

          <div key={s.n} className="flex items-start gap-2">

            <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold" style={{ background: 'linear-gradient(135deg,#6366f1,#4f46e5)', color: '#fff', marginTop: 1 }}>{s.n}</div>

            <div>

              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text)', margin: 0 }}>{s.label}</p>

              <p style={{ fontSize: 11, color: 'var(--text-3)', margin: 0, lineHeight: 1.4 }}>{s.desc}</p>

            </div>

          </div>

        ))}

      </div>

    </div>

  );

}



// ─── Technique Selector (Step 5) ─────────────────────────────────────

function TechniqueSelector({

  autoSelect,

  setAutoSelect,

  selected,

  setSelected,

  dataDictionary,

  brief,

  studyTypes,

}: {

  autoSelect: boolean;

  setAutoSelect: (v: boolean) => void;

  selected: Set<string>;

  setSelected: (s: Set<string>) => void;

  dataDictionary: DataDictionary | null;

  brief: any;

  studyTypes: string[];

}) {

  const [search, setSearch] = useState('');

  const [expanded, setExpanded] = useState<Set<string>>(new Set(['descriptive', 'parametric', 'correlation']));

  const [dismissedWarnings, setDismissedWarnings] = useState<Set<string>>(new Set());



  const toggle = (id: string) => {

    const next = new Set(selected);

    next.has(id) ? next.delete(id) : next.add(id);

    setSelected(next);

  };



  const toggleGroup = (groupId: string, ids: string[]) => {

    const allSelected = ids.every(id => selected.has(id));

    const next = new Set(selected);

    if (allSelected) ids.forEach(id => next.delete(id));

    else ids.forEach(id => next.add(id));

    setSelected(next);

  };



  const toggleExpand = (groupId: string) => {

    const next = new Set(expanded);

    next.has(groupId) ? next.delete(groupId) : next.add(groupId);

    setExpanded(next);

  };



  const totalSelected = selected.size;

  const q = search.toLowerCase();



  const filtered = TECHNIQUE_GROUPS.map(g => ({

    ...g,

    techniques: q

      ? g.techniques.filter(t => t.label.toLowerCase().includes(q) || t.desc.toLowerCase().includes(q))

      : g.techniques,

  })).filter(g => g.techniques.length > 0);



  // Build a map of incompatible selected techniques for the warning banner

  const selectedIncompatible: Array<{ id: string; label: string; reasons: string[] }> = [];

  if (!autoSelect && dataDictionary) {

    for (const group of TECHNIQUE_GROUPS) {

      for (const tech of group.techniques) {

        if (selected.has(tech.id)) {

          const { compatible, reasons } = checkCompatibility((tech as any).requires ?? {}, dataDictionary, brief);



          if (!compatible && !dismissedWarnings.has(tech.id)) {

            selectedIncompatible.push({ id: tech.id, label: tech.label, reasons });

          }

        }

      }

    }

  }



  return (

    <div className="space-y-4">

      {/* Incompatibility warning banner */}

      {selectedIncompatible.length > 0 && (

        <div className="rounded-xl p-4 space-y-3"

          style={{ background: 'rgba(239,68,68,0.06)', border: '1.5px solid rgba(239,68,68,0.3)' }}>

          <div className="flex items-start gap-2">

            <RiErrorWarningFill size={16} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: 1 }} />

            <div className="flex-1">

              <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--danger)', margin: '0 0 6px' }}>

                {selectedIncompatible.length} selected test{selectedIncompatible.length > 1 ? 's' : ''} may be incompatible with your dataset

              </p>

              {selectedIncompatible.map(t => (

                <div key={t.id} className="mb-3">

                  <div className="flex items-center gap-2 mb-1">

                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>{t.label}</span>

                    <button

                      onClick={() => { const next = new Set(selected); next.delete(t.id); setSelected(next); }}

                      className="text-xs px-2 py-0.5 rounded-md font-semibold"

                      style={{ background: 'rgba(239,68,68,0.12)', color: 'var(--danger)', border: '1px solid rgba(239,68,68,0.25)' }}

                    >Remove</button>

                    <button

                      onClick={() => setDismissedWarnings(p => new Set(Array.from(p).concat(t.id)))}

                      className="text-xs px-2 py-0.5 rounded-md font-semibold ml-auto"

                      style={{ background: 'rgba(245,158,11,0.1)', color: 'var(--warning)', border: '1px solid rgba(245,158,11,0.25)' }}

                    >Keep anyway</button>

                  </div>

                  <ul className="pl-3 space-y-0.5">

                    {t.reasons.map((r, i) => (

                      <li key={i} style={{ fontSize: 11, color: 'var(--text-2)', listStyle: 'disc' }}>{r}</li>

                    ))}

                  </ul>

                </div>

              ))}

            </div>

          </div>

        </div>

      )}

      {/* Mode toggle */}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">

        {[

          {

            val: true,

            title: 'AI Auto-Select',

            desc: 'AI analyses your topic, objectives, hypotheses, study design, variable types, and sample size to select the optimal test suite',

            icon: RiSparklingFill,

            color: '#6366f1',

          },

          {

            val: false,

            title: 'I Choose My Tests',

            desc: 'Manually select the exact statistical techniques to run from the full catalogue',

            icon: RiCpuFill,

            color: '#10b981',

          },

        ].map(opt => {

          const Icon = opt.icon;

          const active = autoSelect === opt.val;

          return (

            <button

              key={String(opt.val)}

              onClick={() => setAutoSelect(opt.val)}

              className="rounded-xl p-4 text-left transition-all duration-150"

              style={{

                background: active ? `${opt.color}12` : 'var(--surface-2)',

                border: `2px solid ${active ? opt.color + '60' : 'var(--border)'}`,

                boxShadow: active ? `0 0 0 3px ${opt.color}15` : 'none',

              }}

            >

              <div className="flex items-center gap-2 mb-2">

                <div className="w-8 h-8 rounded-lg flex items-center justify-center"

                  style={{ background: active ? opt.color + '20' : 'var(--surface)' }}>

                  <Icon size={17} style={{ color: active ? opt.color : 'var(--text-3)' }} />

                </div>

                <div className="w-4 h-4 rounded-full border-2 flex items-center justify-center ml-auto"

                  style={{ borderColor: active ? opt.color : 'var(--border)' }}>

                  {active && <div className="w-2 h-2 rounded-full" style={{ background: opt.color }} />}

                </div>

              </div>

              <p style={{ fontSize: 13, fontWeight: 700, color: active ? 'var(--text)' : 'var(--text-2)', margin: '0 0 4px' }}>

                {opt.title}

              </p>

              <p style={{ fontSize: 11, color: 'var(--text-3)', lineHeight: 1.5 }}>{opt.desc}</p>

            </button>

          );

        })}

      </div>



      {/* Manual selection panel */}

      {!autoSelect && (

        <div className="space-y-3 animate-slide-up">

          {/* Header + search */}

          <div className="flex items-center gap-3">

            <div className="flex-1 relative group">

              <RiSearchEyeFill size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors" style={{ color: 'var(--brand)' }} />

              <input

                className="w-full pl-10 pr-4 py-3 rounded-xl outline-none transition-all focus:ring-4 focus:ring-indigo-500/20"

                placeholder="Search techniques (e.g. ANOVA, T-test)..."

                value={search}

                onChange={e => setSearch(e.target.value)}

                style={{

                  fontSize: 14,

                  background: 'var(--surface)',

                  border: '2px solid var(--brand)',

                  color: 'var(--text)',

                  boxShadow: '0 2px 10px rgba(99,102,241,0.1)'

                }}

              />

            </div>

            {totalSelected > 0 && (

              <div className="px-3 py-1.5 rounded-lg flex items-center gap-1.5"

                style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)' }}>

                <RiCheckboxCircleFill size={13} style={{ color: 'var(--brand)' }} />

                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--brand)' }}>{totalSelected} selected</span>

              </div>

            )}

          </div>



          {/* AI suitability note */}

          {/* AI suitability note */}

          <div className="flex items-start gap-3 p-4 rounded-xl shadow-sm"

            style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.4)' }}>

            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style={{ background: 'var(--border)' }}>

              <RiErrorWarningFill size={16} style={{ color: '#d97706' }} />

            </div>

            <div>

              <p style={{ fontSize: 13, fontWeight: 700, color: '#b45309', marginBottom: 2 }}>AI Validation</p>

              <p style={{ fontSize: 13, color: '#92400e', lineHeight: 1.5 }}>

                {dataDictionary

                  ? 'Tests marked ⚠ may be incompatible with your data. You can keep them, but AI will double-check during execution.'

                  : 'AI will verify your chosen tests against your data and warn you if they are statistically inappropriate.'}

              </p>

            </div>

          </div>



          {/* Technique groups */}

          <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1"

            style={{ scrollbarWidth: 'thin' }}>

            {filtered.map(group => {

              const GroupIcon = group.icon;

              const ids = group.techniques.map(t => t.id);

              const allChosen = ids.every(id => selected.has(id));

              const someChosen = ids.some(id => selected.has(id));

              const isOpen = expanded.has(group.id);

              const chosenCount = ids.filter(id => selected.has(id)).length;

              // Incompatible count in this group based on data dictionary

              const incompatCount = group.techniques.filter(t =>

                selected.has(t.id) &&

                !checkCompatibility((t as any).requires ?? {}, dataDictionary, brief).compatible



              ).length;



              return (

                <div key={group.id} className="rounded-xl overflow-hidden"

                  style={{ border: `1px solid ${someChosen ? group.color + '40' : 'var(--border)'}`, background: 'var(--surface)' }}>



                  {/* Group header */}

                  <div

                    className="flex items-center gap-3 p-3 cursor-pointer select-none"

                    style={{ background: someChosen ? `${group.color}08` : 'transparent' }}

                  >

                    {/* Group checkbox */}

                    <button

                      onClick={() => toggleGroup(group.id, ids)}

                      className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0 transition-all"

                      style={{

                        background: allChosen ? group.color : someChosen ? `${group.color}30` : 'var(--surface-2)',

                        border: `2px solid ${someChosen || allChosen ? group.color : 'var(--border)'}`,

                      }}

                    >

                      {allChosen && <RiCheckboxCircleFill size={12} color="#fff" />}

                      {someChosen && !allChosen && <div className="w-2 h-0.5 rounded" style={{ background: group.color }} />}

                    </button>



                    {/* Group icon + label */}

                    <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"

                      style={{ background: `${group.color}18` }}>

                      <GroupIcon size={15} style={{ color: group.color }} />

                    </div>

                    <div className="flex-1 min-w-0" onClick={() => toggleExpand(group.id)}>

                      <div className="flex items-center gap-2">

                        <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', margin: 0 }}>{group.label}</p>

                        {chosenCount > 0 && (

                          <span className="px-1.5 py-0.5 rounded-md text-xs font-bold"

                            style={{ background: `${group.color}20`, color: group.color }}>

                            {chosenCount}/{ids.length}

                          </span>

                        )}

                        {incompatCount > 0 && (

                          <span className="px-1.5 py-0.5 rounded-md text-xs font-bold flex items-center gap-1"

                            style={{ background: 'rgba(239,68,68,0.12)', color: 'var(--danger)' }}>

                            ⚠ {incompatCount} may not fit

                          </span>

                        )}

                      </div>

                      <p style={{ fontSize: 11, color: 'var(--text-3)', margin: 0 }}>{group.desc}</p>

                    </div>

                    <button onClick={() => toggleExpand(group.id)} style={{ color: 'var(--text-3)', flexShrink: 0 }}>

                      {isOpen ? <RiArrowUpSFill size={15} /> : <RiArrowDownSFill size={15} />}

                    </button>

                  </div>



                  {/* Technique list */}

                  {isOpen && (

                    <div style={{ borderTop: `1px solid ${group.color}25` }}>

                      {group.techniques.map((tech, i) => {

                        const checked = selected.has(tech.id);

                        const { compatible, reasons } = checkCompatibility((tech as any).requires ?? {}, dataDictionary, brief);



                        const isWarn = !compatible && !dismissedWarnings.has(tech.id);

                        return (

                          <button

                            key={tech.id}

                            onClick={() => toggle(tech.id)}

                            className="w-full flex items-start gap-3 px-3 py-2.5 text-left transition-all"

                            style={{

                              background: checked

                                ? isWarn ? 'rgba(239,68,68,0.06)' : `${group.color}08`

                                : i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.01)',

                              borderTop: i > 0 ? '1px solid var(--border)' : 'none',

                            }}

                          >

                            {/* Checkbox */}

                            <div

                              className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 mt-0.5 transition-all"

                              style={{

                                background: checked ? (isWarn ? '#ef4444' : group.color) : 'var(--surface-2)',

                                border: `2px solid ${checked ? (isWarn ? '#ef4444' : group.color) : 'var(--border)'}`,

                              }}

                            >

                              {checked && <RiCheckboxCircleFill size={10} color="#fff" />}

                            </div>

                            <div className="flex-1 min-w-0">

                              <div className="flex items-center gap-2">

                                <p style={{ fontSize: 12, fontWeight: checked ? 700 : 500, color: checked ? 'var(--text)' : 'var(--text-2)', margin: 0 }}>

                                  {tech.label}

                                </p>

                                {isWarn && (

                                  <span title={reasons.join('; ')}

                                    className="text-xs px-1.5 py-0.5 rounded font-bold flex-shrink-0"

                                    style={{ background: 'rgba(239,68,68,0.1)', color: 'var(--danger)' }}>⚠ may not fit</span>

                                )}

                              </div>

                              <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '1px 0 0', lineHeight: 1.4 }}>

                                {tech.desc}

                              </p>

                              {isWarn && checked && (

                                <ul className="mt-1 pl-3" style={{ fontSize: 10, color: 'var(--danger)', opacity: 0.85 }}>

                                  {reasons.map((r, ri) => <li key={ri} style={{ listStyle: 'disc' }}>{r}</li>)}

                                </ul>

                              )}

                            </div>

                          </button>

                        );

                      })}

                    </div>

                  )}

                </div>

              );

            })}



            {filtered.length === 0 && (

              <div className="text-center py-8" style={{ color: 'var(--text-3)' }}>

                <RiSearchEyeFill size={24} className="mx-auto mb-2 opacity-40" />

                <p style={{ fontSize: 13 }}>No techniques match "{search}"</p>

              </div>

            )}

          </div>





        </div>

      )}



      {/* AI Intelligence Panel — comprehensive reasoning display */}

      {autoSelect && (

        <AutoSelectReasoningPanel

          brief={brief}

          dataDictionary={dataDictionary}

          studyTypes={studyTypes}

        />

      )}

    </div>

  );

}



// ─── Data Quality Panel ────────────────────────────────────────────────────

function DataQualityPanel({ report }: { report: any }) {

  const [expanded, setExpanded] = React.useState(false);

  if (!report) return null;



  const score = report.data_quality_score ?? 0;

  const label = report.quality_label ?? 'Unknown';

  const scoreColor = score >= 90 ? '#10b981' : score >= 75 ? '#6366f1' : score >= 55 ? '#f59e0b' : '#ef4444';

  const cols: Record<string, any> = report.column_profiles ?? {};

  const colKeys = Object.keys(cols);

  const actions: any[] = report.actions_taken ?? [];

  const skewed: string[] = report.skewed_columns ?? [];

  const imbalance: Record<string, any> = report.class_imbalance ?? {};

  const inconsistencies: Record<string, any> = report.inconsistencies ?? {};



  // Summary counts

  const totalIssues = colKeys.filter(k => (cols[k]?.issues ?? []).length > 0).length;

  const missingCols = colKeys.filter(k => (cols[k]?.pct_missing ?? 0) > 5).length;

  const outlierCols = Object.keys(report.outliers ?? {}).length;

  const imbalancedCols = Object.values(imbalance).filter((v: any) => v.imbalanced).length;



  return (

    <div style={{ borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden', marginTop: 4 }}>

      {/* ── Header: Score + Overview ── */}

      <div style={{ padding: '14px 16px', background: 'linear-gradient(135deg, rgba(99,102,241,0.07) 0%, rgba(16,185,129,0.04) 100%)', borderBottom: '1px solid var(--border)' }}>

        <div className="flex items-center justify-between gap-3 mb-2">

          <div className="flex items-center gap-2">

            <RiBarChart2Fill size={14} style={{ color: 'var(--brand)' }} />

            <span style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 13, color: 'var(--text)' }}>Data Quality Report</span>

          </div>

          <div className="flex items-center gap-2">

            <span style={{ fontSize: 20, fontWeight: 800, color: scoreColor, fontFamily: 'Syne,sans-serif' }}>{score}</span>

            <span style={{ fontSize: 11, color: scoreColor, fontWeight: 600 }}>/ 100 · {label}</span>

          </div>

        </div>

        {/* Score bar */}

        <div style={{ height: 5, borderRadius: 4, background: 'var(--border)', overflow: 'hidden' }}>

          <div style={{ width: `${score}%`, height: '100%', background: scoreColor, borderRadius: 4, transition: 'width 0.6s ease' }} />

        </div>

        {/* Stats row */}

        <div className="flex items-center gap-4 mt-3 flex-wrap">

          {[

            { label: `${report.shape_after?.rows ?? 0} rows`, icon: '▤' },

            { label: `${report.shape_after?.columns ?? 0} columns`, icon: '▥' },

            { label: `${report.completeness_pct ?? 0}% complete`, icon: '◎' },

            { label: `${report.pct_complete_rows ?? 0}% full rows`, icon: '✓' },

          ].map(s => (

            <span key={s.label} style={{ fontSize: 11, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 4 }}>

              <span style={{ color: 'var(--brand)', fontSize: 10 }}>{s.icon}</span>{s.label}

            </span>

          ))}

        </div>

      </div>



      {/* ── Summary badges ── */}

      <div className="flex flex-wrap gap-2" style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}>

        {actions.map((a: any, i: number) => (

          <span key={i} style={{ fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 20,

            background: a.action === 'duplicates_removed' ? 'rgba(239,68,68,0.12)' : a.action === 'data_types_fixed' ? 'color-mix(in srgb, var(--brand) 10%, transparent)' : 'rgba(245,158,11,0.12)',

            color: a.action === 'duplicates_removed' ? '#ef4444' : a.action === 'data_types_fixed' ? '#6366f1' : '#f59e0b' }}>

            {a.description}

          </span>

        ))}

        {actions.length === 0 && (

          <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 20, background: 'color-mix(in srgb, var(--success) 12%, transparent)', color: '#10b981' }}>

            ✓ No critical issues detected

          </span>

        )}

      </div>



      {/* ── Issue summary row ── */}

      {(missingCols > 0 || outlierCols > 0 || imbalancedCols > 0 || skewed.length > 0 || Object.keys(inconsistencies).length > 0) && (

        <div className="flex flex-wrap gap-3" style={{ padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>

          {missingCols > 0 && <span style={{ fontSize: 11, color: '#f59e0b' }}>⚠ {missingCols} column(s) with missing data</span>}

          {outlierCols > 0 && <span style={{ fontSize: 11, color: '#ef4444' }}>⚠ {outlierCols} column(s) with outliers</span>}

          {skewed.length > 0 && <span style={{ fontSize: 11, color: '#8b5cf6' }}>⟳ {skewed.length} skewed column(s)</span>}

          {imbalancedCols > 0 && <span style={{ fontSize: 11, color: '#ec4899' }}>⚡ {imbalancedCols} imbalanced class column(s)</span>}

          {Object.keys(inconsistencies).length > 0 && <span style={{ fontSize: 11, color: '#6366f1' }}>âš {Object.keys(inconsistencies).length} column(s) with inconsistencies</span>}

        </div>

      )}



      {/* ── Column cards (scrollable) ── */}

      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>

        <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', marginBottom: 8 }}>Column Profiles</p>

        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>

          {colKeys.slice(0, expanded ? colKeys.length : 12).map(col => {

            const p = cols[col];

            const hasIssues = (p?.issues ?? []).length > 0;

            const inferColor = p?.inferred_type === 'continuous' ? '#6366f1' : p?.inferred_type === 'categorical' ? '#10b981' : p?.inferred_type === 'datetime' ? '#3b82f6' : p?.inferred_type === 'binary' ? '#ec4899' : '#f59e0b';

            return (

              <div key={col} style={{

                minWidth: 110, maxWidth: 110, borderRadius: 8, padding: '8px 10px',

                background: hasIssues ? 'var(--surface-2)' : 'var(--surface-2)',

                border: `1px solid ${hasIssues ? 'rgba(245,158,11,0.25)' : 'var(--border)'}`,

                flexShrink: 0,

              }}>

                <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--text)', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={col}>{col}</p>

                <span style={{ fontSize: 9, fontWeight: 600, padding: '1px 5px', borderRadius: 4, background: `${inferColor}18`, color: inferColor, display: 'inline-block', marginTop: 3 }}>

                  {p?.inferred_type ?? p?.dtype ?? '?'}

                </span>

                {p?.pct_missing > 0 && <p style={{ fontSize: 9, color: '#f59e0b', margin: '3px 0 0' }}>{p.pct_missing}% missing</p>}

                {p?.n_outliers_iqr > 0 && <p style={{ fontSize: 9, color: '#ef4444', margin: '2px 0 0' }}>{p.n_outliers_iqr} outliers</p>}

                {(p?.issues ?? []).length === 0 && <p style={{ fontSize: 9, color: '#10b981', margin: '3px 0 0' }}>✓ clean</p>}

              </div>

            );

          })}

        </div>

        {colKeys.length > 12 && (

          <button onClick={() => setExpanded(e => !e)} style={{ fontSize: 11, color: 'var(--brand)', background: 'none', border: 'none', cursor: 'pointer', marginTop: 6, padding: 0 }}>

            {expanded ? '▲ Show less' : `▼ Show all ${colKeys.length} columns`}

          </button>

        )}

      </div>



      {/* ── Missing strategies ── */}

      {missingCols > 0 && (

        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'rgba(245,158,11,0.03)' }}>

          <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', marginBottom: 6 }}>Missing Value Strategies</p>

          <div className="space-y-1">

            {Object.entries(report.missing_per_column ?? {})

              .filter(([, v]: any) => v.pct_missing > 0)

              .slice(0, 5)

              .map(([col, v]: any) => (

                <div key={col} className="flex items-center justify-between gap-2">

                  <span style={{ fontSize: 11, color: 'var(--text)', fontWeight: 500 }}>{col}</span>

                  <div className="flex items-center gap-2">

                    <span style={{ fontSize: 10, color: '#f59e0b' }}>{v.pct_missing}%</span>

                    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(99,102,241,0.1)', color: '#6366f1', fontWeight: 600 }}>

                      {v.recommended_strategy?.replace(/_/g, ' ')}

                    </span>

                    {v.mnar_risk && <span style={{ fontSize: 10, color: '#ec4899', fontWeight: 600 }}>MNAR risk</span>}

                  </div>

                </div>

              ))}

          </div>

        </div>

      )}



      {/* ── Outlier summary ── */}

      {outlierCols > 0 && (

        <div style={{ padding: '10px 16px', background: 'rgba(239,68,68,0.02)' }}>

          <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', marginBottom: 6 }}>Outlier Summary</p>

          <div className="space-y-1">

            {Object.entries(report.outliers ?? {}).slice(0, 4).map(([col, v]: any) => (

              <div key={col} className="flex items-center justify-between gap-2">

                <span style={{ fontSize: 11, color: 'var(--text)', fontWeight: 500 }}>{col}</span>

                <div className="flex items-center gap-3">

                  <span style={{ fontSize: 10, color: '#ef4444' }}>IQR: {v.n_outliers_iqr}</span>

                  <span style={{ fontSize: 10, color: '#f59e0b' }}>Z-score: {v.n_outliers_zscore}</span>

                  <span style={{ fontSize: 10, color: 'var(--text-3)' }}>{v.pct_outliers}%</span>

                </div>

              </div>

            ))}

          </div>

        </div>

      )}

    </div>

  );

}



// ─── Main Page ────────────────────────────────────────────────────────

export default function AnalysisIndexPage() {

  const router = useRouter();

  const { data: jobsData, isLoading, mutate: mutateJobs } = useSWR('/analysis/jobs', { refreshInterval: 5000 });

  const jobs: any[] = jobsData || [];

  const loading = isLoading;

  const [uploading, setUploading] = useState(false);

  const [currentStep, setCurrentStep] = useState(1);

  const [touched, setTouched] = useState(false);

  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [chaptersDoc, setChaptersDoc] = useState<File | null>(null);

  const [showChapters, setShowChapters] = useState(false);

  const [showExtra, setShowExtra] = useState(false);

  const [reportType, setReportTypeRaw] = useState(() => {

    if (typeof window !== 'undefined') {

      return localStorage.getItem('rf_preferred_report_type') || 'business_report';

    }

    return 'business_report';

  });

  const setReportType = (val: string) => {

    setReportTypeRaw(val);

    if (typeof window !== 'undefined') {

      localStorage.setItem('rf_preferred_report_type', val);

    }

  };

  const [academicTradition, setAcademicTradition] = useState('standard');

  const [formattingOptions, setFormattingOptions] = useState<any>({});



  // Initialize from preferences on mount

  useEffect(() => {

    try {

      const userStr = localStorage.getItem('rf_user');

      if (userStr) {

        const user = JSON.parse(userStr);

        if (user.preferences) {

          if (user.preferences.academic_tradition) {

            setAcademicTradition(user.preferences.academic_tradition);

          }

          setFormattingOptions(user.preferences);

        }

      }

    } catch(e) {}

  }, []);



  const [dataFile, setDataFile] = useState<File | null>(null);

  const [dataDictionary, setDataDictionary] = useState<any>(null);

  const [inspectionReport, setInspectionReport] = useState<any>(null);

  const [inspecting, setInspecting] = useState(false);

  const [marketplaceLoading, setMarketplaceLoading] = useState(false);

  const [marketplaceSource, setMarketplaceSource] = useState<string | null>(null);

  const [creditEstimate, setCreditEstimate] = useState<CreditEstimate | null>(null);

  const [estimateLoading, setEstimateLoading] = useState(false);



  // Techniques state

  const [autoSelect, setAutoSelect] = useState(true);

  const [scaleMode, setScaleMode] = useState<'auto' | 'manual'>('auto');

  // AI Variable Advisor State
  const [advisorLoading, setAdvisorLoading] = useState(false);
  const [advisorResult, setAdvisorResult] = useState<any>(null);
  const [advisorApplied, setAdvisorApplied] = useState(false);

  // AI Scale Advisor State
  const [scaleAdvisorLoading, setScaleAdvisorLoading] = useState(false);
  const [scaleAdvisorResult, setScaleAdvisorResult] = useState<any>(null);

  const [constructMode, setConstructMode] = useState<'auto' | 'manual'>('auto');

  const [selectedTechniques, setSelectedTechniques] = useState<Set<string>>(new Set());



  // Multi-strand & new fields

  const [studyTypes, setStudyTypes] = useState<string[]>(['quantitative']);

  const [sampleSize, setSampleSize] = useState<string>('');

  const [qualFiles, setQualFiles] = useState<File[]>([]);

  const [qualCodingApproach, setQualCodingApproach] = useState<'inductive' | 'deductive' | 'abductive'>('inductive');

  const [qualMinThemes, setQualMinThemes] = useState<number>(3);

  const [hasPretest, setHasPretest] = useState(false);

  const [hasControl, setHasControl] = useState(false);

  const [nCases, setNCases] = useState(1);

  const [caseApproach, setCaseApproach] = useState<'within' | 'cross' | 'descriptive' | 'explanatory' | 'exploratory' | 'intrinsic' | 'instrumental'>('within');



  // Visualization

  const [autoViz, setAutoViz] = useState(true);

  const [selectedViz, setSelectedViz] = useState<Set<string>>(new Set());



  // Tables

  const [autoTables, setAutoTables] = useState(true);

  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());



  const hasQualitative = studyTypes.includes('qualitative') || studyTypes.includes('mixed');

  const hasQuantitative = studyTypes.some(t => ['quantitative','descriptive','experimental','correlation','mixed','trend','segmentation','survey'].includes(t));

  const hasExperimental = studyTypes.includes('experimental');

  const hasCaseStudy = studyTypes.includes('case_study');



  const toggleStudyType = (type: string) => {

    setStudyTypes(prev => {

      let next = prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type];



      if (type === 'mixed' && next.includes('mixed')) {

        next = next.filter(t => t !== 'quantitative' && t !== 'qualitative');

      } else if (type === 'quantitative' || type === 'qualitative') {

        next = next.filter(t => t !== 'mixed');

      }



      return next;

    });

  };



  const toggleViz = (id: string) => {

    setSelectedViz(prev => {

      const next = new Set(prev);

      next.has(id) ? next.delete(id) : next.add(id);

      return next;

    });

  };



  const toggleTable = (id: string) => {

    setSelectedTables(prev => {

      const next = new Set(prev);

      next.has(id) ? next.delete(id) : next.add(id);

      return next;

    });

  };



  const [brief, setBrief] = useState<any>({

    topic: '', population: '', study_type: 'quantitative',

    dependent_variable: '', independent_variable: '', control_variable: '',

    mediating_variable: '', moderating_variable: '',

    nesting_variable: '',

    research_background: '', problem_statement: '', study_aim: '',

    user_class: '',

    research_design: '',

    variable_scales: {} as Record<string, string>,

    likert_constructs: [] as Array<{ name: string; columns: string[] }>,

    objectives: [''], research_questions: [''], hypotheses: [''], significance_level: 0.05,

  });



  const [constructsOpen, setConstructsOpen] = React.useState(false);



  const hasSurveyId = !!router.query.surveyId;

  const stepErrors = validateStep(currentStep, brief, dataFile, hasSurveyId);

  const isStepValid = Object.keys(stepErrors).length === 0;

  const allErrors   = { ...validateStep(1, brief, dataFile, hasSurveyId), ...validateStep(2, brief), ...validateStep(3, brief), ...validateStep(4, brief) };

  const allValid    = Object.keys(allErrors).length === 0;



  // Step 4 validity: auto-select always valid; manual requires ≥1 selection

  const step4Valid  = autoSelect || selectedTechniques.size > 0;



  const canGoNext = () => {

    if (currentStep === 5) return step4Valid;

    return isStepValid;

  };



  // Removed manual fetchJobs; SWR handles data fetching and background updates



  useEffect(() => {

    if (currentStep < 5) return;

    setEstimateLoading(true);

    creditsApi

      .estimate({

        study_types: studyTypes,

        auto_select_techniques: autoSelect,

        technique_count: selectedTechniques.size,

        qualitative_file_count: qualFiles.length,

        has_chapters_doc: !!chaptersDoc,

        report_type: reportType,

      })

      .then((res) => setCreditEstimate(res.data))

      .catch(() => setCreditEstimate(null))

      .finally(() => setEstimateLoading(false));

  }, [

    currentStep,

    studyTypes,

    autoSelect,

    selectedTechniques.size,

    qualFiles.length,

    chaptersDoc,

    reportType,

  ]);



  useEffect(() => {

    if (!router.isReady || router.query.source !== 'marketplace') return;



    const slug = typeof router.query.slug === 'string' ? router.query.slug : undefined;

    const token = typeof router.query.token === 'string' ? router.query.token : undefined;

    const titleFromQuery = typeof router.query.title === 'string' ? router.query.title : undefined;



    if (!slug && !token) return;



    let cancelled = false;



    (async () => {

      setMarketplaceLoading(true);

      setMarketplaceSource(titleFromQuery || slug || 'Marketplace dataset');

      setCurrentStep(1);



      try {

        const { file, dataset } = await importMarketplaceDataset({ slug, downloadToken: token });

        if (cancelled) return;



        const prefill = briefFromMarketplaceDataset({

          ...dataset,

          title: titleFromQuery || dataset.title,

        });

        setBrief((b: any) => ({ ...b, ...prefill }));

        setMarketplaceSource(dataset.title || titleFromQuery || file.name);



        const fd = new FormData();

        fd.append('file', file);

        const res = await analysisApi.inspectFile(fd);

        if (cancelled) return;



        setDataDictionary(res.data.data_dictionary);

        setDataFile(file);

        setCurrentStep(2);

        toast.success('Marketplace dataset loaded — review your project brief');



        router.replace('/analysis', undefined, { shallow: true });

      } catch (err: unknown) {

        if (cancelled) return;

        if (err instanceof MarketplaceImportError) {

          if (err.code === 'PURCHASE_REQUIRED' && slug) {

            toast.error(err.message);

            router.push(`/marketplace/datasets/${slug}/purchase`);

            return;

          }

          toast.error(err.message);

        } else {

          toast.error('Failed to load marketplace dataset');

        }

        router.replace('/analysis', undefined, { shallow: true });

      } finally {

        if (!cancelled) setMarketplaceLoading(false);

      }

    })();



    return () => {

      cancelled = true;

    };

  // eslint-disable-next-line react-hooks/exhaustive-deps

  }, [router.isReady, router.query.source, router.query.slug, router.query.token, router.query.title]);



  // Load survey metadata & questions into dataDictionary when launching analysis from a survey

  // Layer 1: Auto-trigger AI Variable Advisor when student reaches Step 4
  useEffect(() => {
    if (currentStep === 4) {
      const hasRQs = brief.research_questions?.some((q: string) => q && q.trim().length > 0);
      if (hasRQs && !advisorResult && !advisorLoading) {
        const timer = setTimeout(() => handleVariableAdvisor(), 500);
        return () => clearTimeout(timer);
      }
    }
  }, [currentStep]); // eslint-disable-line react-hooks/exhaustive-deps


  useEffect(() => {

    if (!router.isReady || !router.query.surveyId) return;

    const sId = router.query.surveyId as string;

    Promise.all([

      surveysApi.get(sId),

      questionsApi.list(sId)

    ]).then(([svRes, qsRes]) => {

      const qs = qsRes.data || [];

      const dict: Record<string, any> = {};

      qs.forEach((q: any, i: number) => {

        if (q.type !== 'section_header') {

          const varName = q.variable_name || `q${i + 1}`;

          // Normalise measurement_level to the same "level" field used by file upload

          // so checkCompatibility works identically for both survey and file paths.

          const rawType = q.measurement_level || q.type || 'nominal';

          let level: string;

          if (['ratio', 'interval', 'continuous'].includes(rawType)) level = 'continuous';

          else if (rawType === 'ordinal') level = 'ordinal';

          else if (['number', 'slider', 'constant_sum', 'rating'].includes(q.type)) level = 'continuous';

          else if (['likert', 'matrix'].includes(q.type)) level = 'ordinal';

          else level = 'nominal';



          // Estimate n_unique from question type for group-col detection

          let n_unique = 0;

          if (q.type === 'multiple_choice' && q.options) n_unique = q.options.length;

          else if (q.type === 'yes_no' || q.type === 'binary') n_unique = 2;

          else if (q.type === 'likert') n_unique = q.scale || 5;

          else if (level === 'nominal') n_unique = 5;   // conservative estimate

          else n_unique = 50;                            // continuous — won't trigger group



          dict[varName] = {

            level,

            type:  rawType,

            label: q.text || `Question ${i + 1}`,

            question_type: q.type,

            n_unique,

            n_rows:    0,   // unknown at this stage; rows check won't block

            n_missing: 0,

          };

        }

      });

      setDataDictionary(dict);

      if (svRes.data?.title) {

        setBrief((b: any) => (b.topic ? b : { ...b, topic: svRes.data.title }));

      }

    }).catch(err => {

      console.error('Failed to load survey metadata for analysis wizard', err);

    });

  }, [router.isReady, router.query.surveyId]);



  const update = (key: string, val: any) => setBrief((b: any) => ({ ...b, [key]: val }));



  const wizardTopRef = React.useRef<HTMLDivElement>(null);



  const scrollToWizardTop = () => {

    if (wizardTopRef.current) {

      const yOffset = -90;

      const y = wizardTopRef.current.getBoundingClientRect().top + window.pageYOffset + yOffset;

      window.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });

    } else {

      window.scrollTo({ top: 0, behavior: 'smooth' });

    }

  };



  const goNext = () => {

    if (currentStep !== 5) { setTouched(true); if (!isStepValid) return; }

    else { if (!step4Valid) { toast.error('Select at least one technique or use AI Auto-Select'); return; } }

    setTouched(false);

    setCurrentStep(s => Math.min(s + 1, STEPS.length));

    setTimeout(scrollToWizardTop, 50);

  };



  const goPrev = () => { 

    setTouched(false); 

    setCurrentStep(s => Math.max(s - 1, 1)); 

    setTimeout(scrollToWizardTop, 50);

  };



  const handleGotoStep = (n: number) => {

    setCurrentStep(n);

    setTimeout(scrollToWizardTop, 50);

  };



  // Lightweight parse — reads column names/types only, no cleaning.

  // Replaces the old handleInspect which ran full clean_and_inspect on upload.

  // ── AI Variable Advisor Handler ──────────────────────────────────────────
  const handleVariableAdvisor = async () => {
    const hasRQs = brief.research_questions?.some((q: string) => q && q.trim().length > 0);
    if (!hasRQs) {
      toast.error('Please enter at least one Research Question in Step 3 (Research) first.', { duration: 5000 });
      return;
    }
    setAdvisorLoading(true);
    setAdvisorResult(null);
    setAdvisorApplied(false);
    try {
      let data;
      try {
        const res = await analysisApi.variableAdvisor({ brief });
        data = res.data;
      } catch (apiErr: any) {
        const token = typeof window !== 'undefined' ? (Cookies.get('rf_token') || localStorage.getItem('auth_token')) : null;
        const resp = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/analysis/variable-advisor`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({ brief })
        });
        if (!resp.ok) {
          const errBody = await resp.json().catch(() => ({}));
          throw new Error(errBody.detail || `Server returned ${resp.status}`);
        }
        data = await resp.json();
      }
      setAdvisorResult(data);
      toast.success('AI recommendations ready!', { icon: '✨' });
    } catch (err: any) {
      console.error('Variable advisor error:', err);
      toast.error(err?.message || 'Unable to fetch AI suggestions. Please check connection or enter variables manually.');
    } finally {
      setAdvisorLoading(false);
    }
  };

  const handleApplyAdvisorVariables = () => {
    if (!advisorResult) return;

    // Apply Dependent Variable
    if (advisorResult.dependent_variable?.name) {
      update('dependent_variable', advisorResult.dependent_variable.name);
    }
    // Apply Independent Variable
    if (advisorResult.independent_variable?.name) {
      update('independent_variable', advisorResult.independent_variable.name);
    }
    // Apply Control Variables (join as comma-separated if multiple)
    const ctrlVars: {name:string}[] = advisorResult.control_variables || [];
    if (ctrlVars.length > 0) {
      const ctrlNames = ctrlVars.map((v: {name:string}) => v.name).filter(Boolean).join(', ');
      if (ctrlNames) update('control_variable', ctrlNames);
    }
    // Apply Mediating Variables (first one; can be expanded later)
    const medVars: {name:string}[] = advisorResult.mediating_variables || [];
    if (medVars.length > 0 && medVars[0]?.name) {
      update('mediating_variable', medVars.map((v: {name:string}) => v.name).filter(Boolean).join(', '));
    }
    // Apply Moderating Variables (first one; can be expanded later)
    const modVars: {name:string}[] = advisorResult.moderating_variables || [];
    if (modVars.length > 0 && modVars[0]?.name) {
      update('moderating_variable', modVars.map((v: {name:string}) => v.name).filter(Boolean).join(', '));
    }

    setAdvisorApplied(true);
    toast.success('All AI-suggested variables populated into fields below!', { duration: 3500 });
  };

  // ── AI Scale Advisor Handler ──────────────────────────────────────────────
  const handleScaleAdvisor = async () => {
    const cols: string[] = dataDictionary ? Object.keys(dataDictionary) : [];
    if (cols.length === 0) {
      toast.error('No dataset loaded. Please upload a file first.', { duration: 4000 });
      return;
    }
    setScaleAdvisorLoading(true);
    setScaleAdvisorResult(null);
    try {
      const columnsMeta = cols.map((name: string) => {
        const info = dataDictionary?.[name] || {};
        return {
          name,
          dtype: info.dtype || 'object',
          n_unique: info.n_unique ?? null,
          sample: (info.sample_values || []).slice(0, 5),
        };
      });
      const token = typeof window !== 'undefined' ? (Cookies.get('rf_token') || localStorage.getItem('auth_token')) : null;
      const resp = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/analysis/scale-advisor`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ brief, columns: columnsMeta }),
      });
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(errBody.detail || `Server returned ${resp.status}`);
      }
      const data = await resp.json();
      setScaleAdvisorResult(data);
      toast.success(`Scale analysis complete — ${Object.keys(data.variable_scales || {}).length} variables classified (${data.source === 'ai' ? 'AI' : 'heuristic'})`, { duration: 4000 });
    } catch (err: any) {
      console.error('Scale advisor error:', err);
      toast.error(err?.message || 'Scale analysis failed. Check connection or enter scales manually.');
    } finally {
      setScaleAdvisorLoading(false);
    }
  };

  const handleApplyScaleAdvisor = (onlyEmpty: boolean = true) => {
    if (!scaleAdvisorResult?.variable_scales) return;
    const next = { ...(brief.variable_scales || {}) };
    for (const [col, info] of Object.entries(scaleAdvisorResult.variable_scales)) {
      const scale = (info as any)?.scale || '';
      if (scale && (!onlyEmpty || !next[col])) {
        next[col] = scale;
      }
    }
    update('variable_scales', next);

    // Also apply constructs if in auto mode
    if (scaleAdvisorResult.likert_constructs?.length > 0 && constructMode === 'auto') {
      const existing = brief.likert_constructs || [];
      const newConstructs = scaleAdvisorResult.likert_constructs
        .filter((c: any) => c.name && c.columns?.length >= 3)
        .map((c: any) => ({ name: c.name, columns: c.columns }));
      if (newConstructs.length > 0 && existing.length === 0) {
        update('likert_constructs', newConstructs);
      }
    }

    toast.success(`Applied ${Object.keys(scaleAdvisorResult.variable_scales).length} scale suggestions`);
  };

  const MAX_FILE_SIZE_MB = 10;


  const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;



  const handleParseColumns = async (file: File) => {

    // ── 10 MB upload gate (client-side) ─────────────────────────────────

    if (file.size > MAX_FILE_SIZE_BYTES) {

      toast.error(

        `File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). ` +

        `Maximum allowed size is ${MAX_FILE_SIZE_MB} MB. ` +

        `Please reduce your dataset size before uploading.`,

        { duration: 7000 }

      );

      return;

    }

    setInspecting(true);

    try {

      const fd = new FormData();

      fd.append('file', file);

      const res = await analysisApi.parseColumns(fd);

      setDataDictionary(res.data.data_dictionary);

      setDataFile(file);

      // No inspection report shown here — that happens in Stage 1 of the pipeline

      toast.success(`File ready — ${res.data.n_rows} rows, ${res.data.n_cols} columns detected`);

    } catch (err: any) {

      toast.error(err.response?.data?.detail || 'Could not parse file columns');

    } finally {

      setInspecting(false);

    }

  };



  const handleRunAnalysis = async () => {

    if (!allValid || (!dataFile && !hasSurveyId)) { toast.error('Please complete all required fields'); setCurrentStep(1); return; }

    if (!step4Valid) { toast.error('Select at least one technique or use AI Auto-Select'); setCurrentStep(5); return; }

    if (hasQualitative && qualFiles.length === 0) {

      toast.error('Please upload at least one interview/transcript file for qualitative analysis');

      setCurrentStep(2); return;

    }

    setUploading(true);

    try {

      const fd = new FormData();

      if (dataFile) fd.append('file', dataFile);

      if (hasSurveyId) fd.append('survey_id', router.query.surveyId as string);

      fd.append('project_brief', JSON.stringify({ ...brief, study_types: studyTypes }));

      fd.append('report_type', reportType);

      fd.append('academic_tradition', academicTradition);

      fd.append('formatting_options', JSON.stringify(formattingOptions));

      fd.append('auto_select_techniques', String(autoSelect));

      fd.append('study_types', JSON.stringify(studyTypes));

      fd.append('sample_size', sampleSize || '');

      fd.append('qual_coding_approach', qualCodingApproach);

      fd.append('qual_min_themes', String(qualMinThemes));

      fd.append('has_pretest_posttest', String(hasPretest));

      fd.append('has_control_group', String(hasControl));

      fd.append('n_cases', String(nCases));

      fd.append('case_analysis_approach', caseApproach);

      fd.append('auto_viz', String(autoViz));

      fd.append('selected_viz', JSON.stringify(Array.from(selectedViz)));

      if (!autoSelect && selectedTechniques.size > 0) {

        fd.append('selected_techniques', JSON.stringify(Array.from(selectedTechniques)));

      }

      fd.append('auto_tables', String(autoTables));

      if (!autoTables) {

        fd.append('selected_tables', JSON.stringify(Array.from(selectedTables)));

      }

      if (chaptersDoc) fd.append('chapters_doc', chaptersDoc);

      qualFiles.forEach(f => fd.append('qualitative_files', f));

      const res = await analysisApi.startFromFile(fd);

      toast.success('Analysis pipeline started!');

      router.push(`/analysis/${res.data.id}`);

    } catch (err: any) {

      toast.error(err.response?.data?.detail || 'Upload failed');

      setUploading(false);

    }

  };



  const handleDeleteJob = async (e: React.MouseEvent, jobId: string) => {

    e.preventDefault(); e.stopPropagation();

    if (!confirm('Delete this analysis? This cannot be undone.')) return;

    setDeletingId(jobId);

    try {

      await analysisApi.deleteJob(jobId);

      toast.success('Analysis deleted');

      mutateJobs();

    } catch { toast.error('Failed to delete'); }

    finally { setDeletingId(null); }

  };



  return (

    <AppLayout

      title="Analysis"

      breadcrumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Analysis' }]}

    >

      {/* ===== GLOBAL PAGE STYLES ===== */}

      <style>{`

        @keyframes slideUpFade {

          from { opacity: 0; transform: translateY(14px); }

          to   { opacity: 1; transform: translateY(0); }

        }

        @keyframes shimmerBar {

          0%   { transform: translateX(-100%); }

          100% { transform: translateX(400%); }

        }

        @keyframes floatPulse {

          0%, 100% { transform: translateY(0px); }

          50%       { transform: translateY(-4px); }

        }

        .wizard-step-content { animation: slideUpFade 0.28s cubic-bezier(0.22,1,0.36,1) both; }

        .job-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.12) !important; }

        .job-card { transition: transform 0.18s ease, box-shadow 0.18s ease; }

        .step-nav-btn:disabled { opacity: 0.45; cursor: not-allowed; }

      `}</style>



      <div style={{ padding: '0 24px 60px', maxWidth: 1400, margin: '0 auto' }}>

        <ResearchWorkflow className="mb-6" />



        {/* ===== TWO-COLUMN LAYOUT ===== */}

        <div className="analysis-layout">



          {/* ============================================================

              LEFT: Research Brief Wizard

          ============================================================ */}

          <div className="analysis-form-panel" ref={wizardTopRef}>



            {/* ── CARD SHELL ── */}

            <div

              style={{

                borderRadius: 0,

                overflow: 'hidden',

                border: '1px solid var(--border)',

                background: 'var(--surface)',

                boxShadow: '0 4px 24px rgba(0,0,0,0.07)',

              }}

            >



              {/* ── GRADIENT HEADER ── */}

              <div

                style={{

                  padding: '22px 28px 0',

                  background:

                    'linear-gradient(135deg, color-mix(in srgb, var(--brand) 10%, transparent) 0%, rgba(79,70,229,0.04) 60%, transparent 100%)',

                  borderBottom: '1px solid var(--border)',

                  position: 'relative',

                  overflow: 'hidden',

                }}

              >

                {/* Decorative orbs */}

                <div style={{

                  position: 'absolute', top: -40, right: -40, width: 140, height: 140,

                  borderRadius: '50%', background: 'color-mix(in srgb, var(--brand) 10%, transparent)',

                  filter: 'blur(30px)', pointerEvents: 'none',

                }} />

                <div style={{

                  position: 'absolute', bottom: -20, left: '40%', width: 80, height: 80,

                  borderRadius: '50%', background: 'color-mix(in srgb, var(--success) 12%, transparent)',

                  filter: 'blur(20px)', pointerEvents: 'none',

                }} />



                {/* Title row */}

                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, position: 'relative' }}>

                  <div style={{

                    width: 40, height: 40, borderRadius: 12,

                    background: 'var(--text)',

                    display: 'flex', alignItems: 'center', justifyContent: 'center',

                    boxShadow: '0 4px 14px rgba(0,0,0,0.1)',

                    animation: 'floatPulse 3s ease-in-out infinite',

                    flexShrink: 0,

                  }}>

                    <RiFlaskFill size={18} color="var(--bg)" />

                  </div>

                  <div style={{ flex: 1 }}>

                    <h2 style={{

                      fontFamily: 'Syne, sans-serif', fontWeight: 800,

                      fontSize: 16, color: 'var(--text)', margin: 0, letterSpacing: '-0.01em',

                    }}>Research Brief</h2>

                    <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '2px 0 0' }}>

                      Step {currentStep} of {STEPS.length} {'\u2014'} {STEPS[currentStep - 1]?.desc}

                    </p>

                  </div>

                  {/* Step counter pill */}

                  <div style={{

                    padding: '4px 12px', borderRadius: 20,

                    background: 'var(--surface-2)',

                    border: '1px solid var(--border)',

                    fontSize: 11, fontWeight: 700, color: 'var(--text)',

                    letterSpacing: '0.02em', flexShrink: 0,

                  }}>

                    {currentStep}/{STEPS.length}

                  </div>

                </div>



                {/* Step bar */}

                <StepBar current={currentStep} onGoto={handleGotoStep} />



                {/* Thin progress line at very bottom of header */}

                <div style={{ height: 3, margin: '0 -28px', background: 'var(--surface-2)', position: 'relative', overflow: 'hidden' }}>

                  <div style={{

                    position: 'absolute', inset: 0,

                    width: `${((currentStep - 1) / (STEPS.length - 1)) * 100}%`,

                    background: 'linear-gradient(90deg, #6366f1, #10b981)',

                    transition: 'width 0.5s cubic-bezier(0.34,1.56,0.64,1)',

                    borderRadius: '0 2px 2px 0',

                  }} />

                </div>

              </div>



              {/* ── STEP CONTENT ── */}

              <div style={{ padding: '28px 28px 0' }}>



                {/* ── Step 1: Upload Data ── */}

                {currentStep === 1 && (

                  <div className="space-y-5 wizard-step-content">

                    <div className="flex items-center gap-2 mb-1">

                      <RiDatabase2Fill size={15} style={{ color: 'var(--brand)' }} />

                      <span style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>Upload Data File</span>

                    </div>

                    {(inspecting || marketplaceLoading) ? (

                      <div className="flex flex-col items-center justify-center py-12 gap-4 rounded-2xl"

                        style={{ background: 'var(--surface-2)', border: '2px dashed var(--brand)' }}>

                        <RiLoader4Line size={40} className="animate-spin" style={{ color: 'var(--brand)' }} />

                        <div className="text-center">

                          <p className="font-bold" style={{ color: 'var(--text)', fontFamily: 'Syne,sans-serif' }}>

                            {marketplaceLoading ? 'Loading from marketplace' : 'Inspecting data'}

                          </p>

                          <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>

                            {marketplaceLoading

                              ? `Fetching ${marketplaceSource || 'dataset'}…`

                              : 'Reading variable names and data types…'}

                          </p>

                        </div>

                      </div>

                    ) : (

                      <>

                        {hasSurveyId && !dataFile && (

                          <div className="mt-4 flex items-center justify-between gap-2 px-4 py-3 rounded-xl" style={{ background: 'color-mix(in srgb, var(--brand) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--brand) 10%, transparent)' }}>

                            <div className="flex items-center gap-3">

                              <RiDatabase2Fill size={18} style={{ color: 'var(--brand)' }} />

                              <div>

                                <p className="text-sm font-semibold truncate" style={{ color: 'var(--text)', margin: 0 }}>Connected to Survey</p>

                                <p className="text-xs" style={{ color: 'var(--brand)', margin: '2px 0 0' }}>Survey data will be used automatically.</p>

                              </div>

                            </div>

                          </div>

                        )}

                        {!hasSurveyId && !marketplaceLoading && <FileDropZone onUpload={handleParseColumns} />}

                        {touched && stepErrors.file && (

                          <p className="text-xs flex items-center gap-1" style={{ color: 'var(--danger)' }}>

                            <RiAlertFill size={12} /> {stepErrors.file}

                          </p>

                        )}

                        {dataFile && (

                          <div className="mt-4">

                            <div className="flex items-center justify-between gap-2 px-4 py-3 rounded-xl" style={{ background: 'color-mix(in srgb, var(--success) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--success) 12%, transparent)' }}>

                              <div className="flex items-center gap-3">

                                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'color-mix(in srgb, var(--success) 12%, transparent)' }}>

                                  <RiFileExcelFill size={20} style={{ color: 'var(--success)' }} />

                                </div>

                                <div>

                                  <p className="text-sm font-bold truncate" style={{ color: 'var(--text)', margin: 0 }}>{dataFile.name}</p>

                                  <p className="text-xs font-medium" style={{ color: 'var(--success)', margin: '2px 0 0' }}>

                                    {(dataFile.size / 1024).toFixed(1)} KB

                                    {dataDictionary && ` · ${Object.keys(dataDictionary).length} columns detected`}

                                  </p>

                                </div>

                              </div>

                              <button className="btn btn-ghost btn-icon hover:bg-red-500/10" style={{ color: 'var(--text-3)' }}

                                onClick={() => { setDataFile(null); setDataDictionary(null); }} title="Remove file">

                                <RiCloseFill size={16} />

                              </button>

                            </div>

                            {dataDictionary && Object.keys(dataDictionary).length > 0 && (

                              <div className="mt-3 p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>

                                <p className="text-xs font-bold mb-2" style={{ color: 'var(--text-2)' }}>Columns detected</p>

                                <div className="flex flex-wrap gap-1.5">

                                  {Object.entries(dataDictionary).slice(0, 12).map(([col, info]: [string, any]) => (

                                    <span key={col} className="px-2 py-0.5 rounded text-xs font-medium"

                                      style={{

                                        background: info.level === 'continuous' ? 'color-mix(in srgb, var(--brand) 10%, transparent)' : info.level === 'ordinal' ? 'color-mix(in srgb, var(--success) 12%, transparent)' : 'color-mix(in srgb, var(--warning) 12%, transparent)',

                                        color: info.level === 'continuous' ? 'var(--brand)' : info.level === 'ordinal' ? 'var(--success)' : 'var(--warning)',

                                        border: `1px solid ${info.level === 'continuous' ? 'color-mix(in srgb, var(--brand) 10%, transparent)' : info.level === 'ordinal' ? 'color-mix(in srgb, var(--success) 12%, transparent)' : 'var(--border)'}`,

                                      }}>{col}</span>

                                  ))}

                                  {Object.keys(dataDictionary).length > 12 && (

                                    <span className="px-2 py-0.5 rounded text-xs" style={{ color: 'var(--text-3)' }}>+{Object.keys(dataDictionary).length - 12} more</span>

                                  )}

                                </div>



                              </div>

                            )}

                          </div>

                        )}

                      </>

                    )}

                  </div>

                )}



                {/* ── Step 2: Project Info ── */}

                {currentStep === 2 && (

                  <div className="space-y-5 wizard-step-content">

                    <div className="flex items-center gap-2 mb-1">

                      <RiFocus2Fill size={15} style={{ color: 'var(--brand)' }} />

                      <span style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>Project / Analysis Details</span>

                    </div>

                    <Field label="Who is this analysis for?" error={touched ? stepErrors.user_class : undefined} hint="This controls the depth of analysis and report style">

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 8 }}>

                        {[

                          { value: 'bsc',        label: 'BSc',        sub: 'Undergraduate' },

                          { value: 'msc',        label: 'MSc',        sub: "Master's" },

                          { value: 'phd',        label: 'PhD',        sub: 'Doctoral' },

                          { value: 'researcher', label: 'Researcher', sub: 'Academic / Independent' },

                          { value: 'business',   label: 'Business',   sub: 'Analyst / Corporate' },

                        ].map(opt => (

                          <button

                            key={opt.value}

                            type="button"

                            onClick={() => update('user_class', opt.value)}

                            style={{

                              padding: '10px 6px',

                              borderRadius: 10,

                              border: brief.user_class === opt.value

                                ? '2px solid var(--brand)'

                                : '1.5px solid var(--border)',

                              background: brief.user_class === opt.value

                                ? 'color-mix(in srgb, var(--brand) 12%, transparent)'

                                : 'var(--input-bg)',

                              cursor: 'pointer',

                              textAlign: 'center',

                              transition: 'all 0.15s',

                            }}

                          >

                            <div style={{ fontWeight: 700, fontSize: 13, color: brief.user_class === opt.value ? 'var(--brand)' : 'var(--text)' }}>{opt.label}</div>

                            <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2 }}>{opt.sub}</div>

                          </button>

                        ))}

                      </div>

                    </Field>



                    <Field label="Research Design" error={touched ? stepErrors.research_design : undefined}

                      hint="How is your study structured? This determines which statistical tests apply">

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>

                        {[

                          { value: 'cross_sectional', label: 'Cross-Sectional',       desc: 'One-time data collection' },

                          { value: 'survey',           label: 'Survey / Questionnaire', desc: 'Structured opinion data' },

                          { value: 'longitudinal',     label: 'Longitudinal',           desc: 'Same group, multiple times' },

                          { value: 'experimental',     label: 'Experimental',           desc: 'Controlled cause & effect' },

                          { value: 'pre_post',         label: 'Pre-test / Post-test',   desc: 'Before & after intervention' },

                          { value: 'correlational',    label: 'Correlational',          desc: 'Relationship analysis' },

                          { value: 'case_study',       label: 'Case Study',             desc: 'In-depth single/few cases' },

                          { value: 'exploratory',      label: 'Exploratory',            desc: 'Discovery, no prior hypothesis' },

                        ].map(opt => (

                          <button

                            key={opt.value}

                            type="button"

                            onClick={() => update('research_design', brief.research_design === opt.value ? '' : opt.value)}

                            style={{

                              padding: '10px 8px',

                              borderRadius: 10,

                              border: brief.research_design === opt.value

                                ? '2px solid var(--brand)'

                                : '1.5px solid var(--border)',

                              background: brief.research_design === opt.value

                                ? 'color-mix(in srgb, var(--brand) 10%, transparent)'

                                : 'var(--input-bg)',

                              cursor: 'pointer',

                              textAlign: 'center',

                              transition: 'all 0.15s',

                            }}

                          >

                            <div style={{ fontWeight: 700, fontSize: 11, color: brief.research_design === opt.value ? 'var(--brand)' : 'var(--text)', lineHeight: 1.2 }}>{opt.label}</div>

                            <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2, lineHeight: 1.2 }}>{opt.desc}</div>

                          </button>

                        ))}

                      </div>

                    </Field>



                    <Field label="Project Title / Analysis Topic" error={touched ? stepErrors.topic : undefined} hint="What is this analysis about?">

                      <textarea id="brief-topic" className="input" rows={2}

                        value={brief.topic} onChange={e => update('topic', e.target.value)}

                        style={{ resize: 'none', borderColor: touched && stepErrors.topic ? 'var(--danger)' : undefined }} />

                    </Field>



                    <Field label="Research Background" required={false}

                      hint="Provide context about what is already known and the gap this study addresses — helps the AI generate a more domain-specific report">

                      <textarea id="brief-bg" className="input" rows={3}

                        value={brief.research_background || ''}

                        onChange={e => update('research_background', e.target.value)}

                        style={{ resize: 'none' }} />

                    </Field>



                    <div className="grid grid-cols-2 gap-4">

                      <Field label="Problem Statement" required={false}

                        hint="State the specific problem or knowledge gap this study investigates">

                        <textarea id="brief-ps" className="input" rows={3}

                          value={brief.problem_statement || ''}

                          onChange={e => update('problem_statement', e.target.value)}

                          style={{ resize: 'none' }} />

                      </Field>

                      <Field label="Study Aim" required={false}

                        hint="State the overall aim of the study in one or two sentences">

                        <textarea id="brief-aim" className="input" rows={3}

                          value={brief.study_aim || ''}

                          onChange={e => update('study_aim', e.target.value)}

                          style={{ resize: 'none' }} />

                      </Field>

                    </div>



                    <div className="grid grid-cols-2 gap-4">

                      <Field label="Target Group / Dataset Context" error={touched ? stepErrors.population : undefined} hint="Who or what does this data represent?">

                        <input id="brief-population" className="input"

                          value={brief.population} onChange={e => update('population', e.target.value)}

                          style={{ borderColor: touched && stepErrors.population ? 'var(--danger)' : undefined }} />

                      </Field>

                      <Field label="Sample / Record Count (n)" required={false} hint="Total rows or participants in the dataset">

                        <input id="brief-sample-size" className="input" type="number" min={1}

                          value={sampleSize}

                          onChange={e => setSampleSize(e.target.value)} />

                      </Field>

                    </div>



                    {/* Analysis Type */}

                    <div>

                      <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-2)', marginBottom: 8 }}>

                        Analysis Type <span style={{ fontWeight: 400, color: 'var(--text-3)' }}>(select all that apply)</span>

                      </p>

                      <div className="grid grid-cols-3 gap-2">

                        {[

                          { id: 'quantitative', label: 'Quantitative',        color: '#6366f1', desc: 'Numbers & statistics' },

                          { id: 'qualitative',  label: 'Qualitative',         color: '#f59e0b', desc: 'Themes & open-ended insights' },

                          { id: 'mixed',        label: 'Mixed Methods',       color: '#8b5cf6', desc: 'Both quant + qual' },

                          { id: 'descriptive',  label: 'Descriptive',         color: '#3b82f6', desc: 'Summarise & profile' },

                          { id: 'experimental', label: 'Experimental / A/B',  color: '#10b981', desc: 'Cause & effect / testing' },

                          { id: 'correlation',  label: 'Correlational',       color: '#ec4899', desc: 'Relationship analysis' },

                          { id: 'trend',        label: 'Trend / Time-Series', color: '#0ea5e9', desc: 'Changes over time' },

                          { id: 'segmentation', label: 'Segmentation',        color: '#a855f7', desc: 'Group comparison & profiling' },

                          { id: 'survey',       label: 'Survey / Opinion',    color: '#f97316', desc: 'Structured opinion data' },

                          { id: 'case_study',   label: 'Case Study',          color: '#14b8a6', desc: 'In-depth single-case analysis' },

                          { id: 'action',       label: 'Process Improvement', color: '#84cc16', desc: 'Cyclical improvement study' },

                        ].map(st => {

                          const active = studyTypes.includes(st.id);

                          return (

                            <button key={st.id} id={`study-type-${st.id}`}

                              onClick={() => toggleStudyType(st.id)}

                              className="rounded-xl p-3 text-left transition-all duration-150"

                              style={{

                                background: active ? `${st.color}18` : 'var(--surface-2)',

                                border: `1.5px solid ${active ? st.color + '60' : 'var(--border)'}`,

                                boxShadow: active ? `0 0 0 2px ${st.color}20` : 'none',

                              }}>

                              <p style={{ fontSize: 11, fontWeight: 700, color: active ? 'var(--text)' : 'var(--text-2)', margin: '3px 0 1px' }}>{st.label}</p>

                              <p style={{ fontSize: 10, color: 'var(--text-3)', margin: 0, lineHeight: 1.3 }}>{st.desc}</p>

                              {active && <div className="mt-1.5 w-4 h-4 rounded-full flex items-center justify-center" style={{ background: st.color, marginLeft: 'auto' }}>

                                <RiCheckboxCircleFill size={10} style={{ color: '#fff' }} /></div>}

                            </button>

                          );

                        })}

                      </div>

                      {studyTypes.length === 0 && (

                        <p className="text-xs mt-1" style={{ color: 'var(--warning)' }}>⚠ Select at least one study type</p>

                      )}

                    </div>



                    <Field label="Significance Level" required={false}>

                      <select className="input" value={brief.significance_level}

                        onChange={e => update('significance_level', parseFloat(e.target.value))}>

                        <option value={0.05}>α = 0.05 (standard)</option>

                        <option value={0.01}>α = 0.01 (strict)</option>

                        <option value={0.10}>α = 0.10 (lenient)</option>

                      </select>

                    </Field>



                    {/* Qualitative Branch */}

                    {hasQualitative && (

                      <div className="rounded-2xl p-6 space-y-5 animate-slide-up relative overflow-hidden"

                        style={{ background: 'var(--surface)', border: '1px solid color-mix(in srgb, var(--warning) 12%, transparent)', boxShadow: '0 4px 12px color-mix(in srgb, var(--warning) 12%, transparent)' }}>

                        

                        <div className="absolute top-0 right-0 w-32 h-32 rounded-full opacity-20 pointer-events-none blur-3xl" style={{ background: '#f59e0b', transform: 'translate(30%, -30%)' }} />

                        <div className="flex items-center gap-2.5">

                          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'color-mix(in srgb, var(--warning) 15%, transparent)' }}>

                            <RiBookOpenFill size={16} style={{ color: '#f59e0b' }} />

                          </div>

                          <div>

                            <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', margin: 0 }}>Qualitative Settings</p>

                            <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '1px 0 0' }}>Thematic analysis & coding configuration</p>

                          </div>

                        </div>

                        <div className="grid grid-cols-2 gap-4">

                          <Field label="Min. Themes" required={false}>

                            <input className="input" type="number" min={1} max={20} value={qualMinThemes}

                              onChange={e => setQualMinThemes(Number(e.target.value))} />

                          </Field>

                          <Field label="Coding Approach" required={false}>

                            <select className="input" value={qualCodingApproach} onChange={e => setQualCodingApproach(e.target.value as 'inductive' | 'deductive' | 'abductive')}>

                              <option value="inductive">Inductive</option>

                              <option value="deductive">Deductive</option>

                              <option value="abductive">Abductive</option>

                            </select>

                          </Field>

                        </div>

                        <div>

                          <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', marginBottom: 10 }}>Transcripts / Open-Ended Responses</p>

                          {qualFiles.length > 0 && (

                            <div className="space-y-2 mb-3">

                              {qualFiles.map((f, i) => (

                                <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg" style={{ background: 'color-mix(in srgb, var(--warning) 12%, transparent)', border: '1px solid var(--border)' }}>

                                  <RiFileFill size={14} style={{ color: '#f59e0b' }} />

                                  <span className="text-xs flex-1 truncate" style={{ color: 'var(--text-2)' }}>{f.name}</span>

                                  <button className="btn btn-ghost btn-icon" onClick={() => setQualFiles(prev => prev.filter((_, idx) => idx !== i))}><RiCloseFill size={13} /></button>

                                </div>

                              ))}

                            </div>

                          )}

                          <label className="flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer transition-all"

                            style={{ background: 'color-mix(in srgb, var(--warning) 12%, transparent)', border: '2px dashed color-mix(in srgb, var(--warning) 12%, transparent)' }}

                            onMouseEnter={e => { e.currentTarget.style.borderColor = '#f59e0b'; e.currentTarget.style.background = 'color-mix(in srgb, var(--warning) 12%, transparent)'; }}

                            onMouseLeave={e => { e.currentTarget.style.borderColor = 'color-mix(in srgb, var(--warning) 12%, transparent)'; e.currentTarget.style.background = 'color-mix(in srgb, var(--warning) 12%, transparent)'; }}>

                            <RiUpload2Fill size={16} style={{ color: '#f59e0b' }} />

                            <span className="text-sm font-semibold" style={{ color: '#f59e0b' }}>Add transcript files</span>

                            <span className="text-xs ml-auto" style={{ color: 'var(--text-3)' }}>.docx, .pdf, .txt</span>

                            <input type="file" multiple className="hidden" accept=".docx,.pdf,.txt"

                              onChange={e => { if (e.target.files) setQualFiles(prev => [...prev, ...Array.from(e.target.files!)]); e.target.value = ''; }} />

                          </label>

                        </div>

                      </div>

                    )}



                    {/* Experimental branch */}

                    {hasExperimental && (

                      <div className="rounded-xl p-4 space-y-4" style={{ background: 'var(--surface-2)', border: '1px solid color-mix(in srgb, var(--success) 12%, transparent)' }}>

                        <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>Experimental Settings</p>

                        <div className="grid grid-cols-2 gap-3">

                          {[{ label: 'Pre-test / Post-test', state: hasPretest, setter: setHasPretest },

                            { label: 'Has Control Group',  state: hasControl, setter: setHasControl }].map(({ label, state, setter }) => (

                            <label key={label} className="flex items-center gap-3 cursor-pointer">

                              <div onClick={() => setter(!state)}

                                className="w-10 h-5 rounded-full transition-all flex items-center relative cursor-pointer"

                                style={{ background: state ? 'var(--success)' : 'var(--border)', padding: 2 }}>

                                <div className="w-4 h-4 rounded-full bg-white transition-all" style={{ transform: state ? 'translateX(20px)' : 'translateX(0)' }} />

                              </div>

                              <span style={{ fontSize: 12, color: 'var(--text-2)', fontWeight: 500 }}>{label}</span>

                            </label>

                          ))}

                        </div>

                      </div>

                    )}



                    {/* Case Study branch */}

                    {hasCaseStudy && (

                      <div className="rounded-xl p-4 space-y-3" style={{ background: 'rgba(20,184,166,0.05)', border: '1px solid rgba(20,184,166,0.2)' }}>

                        <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>Case Study Settings</p>

                        <div className="grid grid-cols-2 gap-3">

                          <Field label="Number of Cases" required={false}>

                            <input className="input" type="number" min={1} value={nCases} onChange={e => setNCases(Number(e.target.value))} />

                          </Field>

                          <Field label="Analysis Approach" required={false}>

                            <select className="input" value={caseApproach} onChange={e => setCaseApproach(e.target.value as 'within' | 'cross' | 'descriptive' | 'explanatory' | 'exploratory' | 'intrinsic' | 'instrumental')}>

                              <option value="descriptive">Descriptive</option>

                              <option value="explanatory">Explanatory</option>

                              <option value="exploratory">Exploratory</option>

                              <option value="intrinsic">Intrinsic</option>

                              <option value="instrumental">Instrumental</option>

                            </select>

                          </Field>

                        </div>

                      </div>

                    )}

                  </div>

                )}



                {/* ── Step 3: Research Design (RQ / Hypotheses / Objectives) ── */}

                {currentStep === 3 && (

                  <div className="space-y-5 wizard-step-content">

                    <div className="flex items-center gap-2 mb-1">

                      <RiBrainFill size={15} style={{ color: 'var(--brand)' }} />

                      <span style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>Research Design</span>

                    </div>

                    {/* Golden Rule: Research Questions FIRST → Hypotheses → Objectives */}

                    <div>

                      <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-2)', marginBottom: 4 }}>Research Questions <span style={{ color: 'var(--danger)', fontSize: 11 }}>*</span></p>

                      <p style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 8 }}>Start here — your research questions drive everything: outcome variable, grouping, and test selection.</p>

                      {brief.research_questions.map((q: string, i: number) => (

                        <div key={i} className="flex gap-2 mb-2">

                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-1" style={{ background: 'rgba(236,72,153,0.1)', fontSize: 11, fontWeight: 700, color: '#ec4899' }}>Q{i + 1}</div>

                          <input className="input flex-1"

                            placeholder={`e.g. RQ${i+1}: Is there a significant difference in GPA between male and female students?`}

                            value={q} onChange={e => update('research_questions', brief.research_questions.map((qq: string, idx: number) => idx === i ? e.target.value : qq))} />

                          {i > 0 && <button className="btn btn-ghost btn-icon" onClick={() => update('research_questions', brief.research_questions.filter((_: any, idx: number) => idx !== i))}><RiCloseFill size={14} /></button>}

                        </div>

                      ))}

                      {touched && stepErrors.research_questions && <p className="text-xs flex items-center gap-1" style={{ color: 'var(--danger)' }}><RiErrorWarningFill size={11} /> {stepErrors.research_questions}</p>}

                      <button className="btn btn-ghost text-xs flex items-center gap-1 mt-1" style={{ color: '#ec4899' }}

                        onClick={() => update('research_questions', [...brief.research_questions, ''])}><RiAddFill size={13} /> Add Research Question</button>

                    </div>

                    <div>

                      <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-2)', marginBottom: 4 }}>Hypotheses <span style={{ color: 'var(--danger)', fontSize: 11 }}>*</span></p>

                      <p style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 8 }}>State your expected findings — derived from your research questions above.</p>

                      {brief.hypotheses.map((h: string, i: number) => (

                        <div key={i} className="flex gap-2 mb-2">

                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-1" style={{ background: 'color-mix(in srgb, var(--success) 12%, transparent)', fontSize: 11, fontWeight: 700, color: 'var(--success)' }}>H{i + 1}</div>

                          <input className="input flex-1"

                            placeholder={`e.g. H${i+1}: There is a significant difference in GPA between male and female students (p < .05)`}

                            value={h} onChange={e => update('hypotheses', brief.hypotheses.map((hh: string, idx: number) => idx === i ? e.target.value : hh))} />

                          {i > 0 && <button className="btn btn-ghost btn-icon" onClick={() => update('hypotheses', brief.hypotheses.filter((_: any, idx: number) => idx !== i))}><RiCloseFill size={14} /></button>}

                        </div>

                      ))}

                      {touched && stepErrors.hypotheses && <p className="text-xs flex items-center gap-1" style={{ color: 'var(--danger)' }}><RiErrorWarningFill size={11} /> {stepErrors.hypotheses}</p>}

                      <button className="btn btn-ghost text-xs flex items-center gap-1 mt-1" style={{ color: 'var(--success)' }}

                        onClick={() => update('hypotheses', [...brief.hypotheses, ''])}><RiAddFill size={13} /> Add Hypothesis</button>

                    </div>

                    <div>

                      <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-2)', marginBottom: 4 }}>Objectives <span style={{ color: 'var(--danger)', fontSize: 11 }}>*</span></p>

                      <p style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 8 }}>What your study aims to achieve — broader goals that the RQs and hypotheses serve.</p>

                      {brief.objectives.map((obj: string, i: number) => (

                        <div key={i} className="flex gap-2 mb-2">

                          <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-1" style={{ background: 'color-mix(in srgb, var(--brand) 10%, transparent)', fontSize: 11, fontWeight: 700, color: 'var(--brand)' }}>{i + 1}</div>

                          <input className="input flex-1"

                            placeholder={`e.g. To examine the relationship between online learning and academic performance among undergraduates`}

                            value={obj} onChange={e => update('objectives', brief.objectives.map((o: string, idx: number) => idx === i ? e.target.value : o))} />

                          {i > 0 && <button className="btn btn-ghost btn-icon" onClick={() => update('objectives', brief.objectives.filter((_: any, idx: number) => idx !== i))}><RiCloseFill size={14} /></button>}

                        </div>

                      ))}

                      {touched && stepErrors.objectives && <p className="text-xs flex items-center gap-1" style={{ color: 'var(--danger)' }}><RiErrorWarningFill size={11} /> {stepErrors.objectives}</p>}

                      <button className="btn btn-ghost text-xs flex items-center gap-1 mt-1" style={{ color: 'var(--brand)' }}

                        onClick={() => update('objectives', [...brief.objectives, ''])}><RiAddFill size={13} /> Add Objective</button>

                    </div>

                  </div>

                )}



                {/* ── Step 4: Variable Mapping (DV / IV driven by RQs above) ── */}
                {currentStep === 4 && (
                  <div className="space-y-5 wizard-step-content">
                    <div className="flex items-center gap-2 mb-1">
                        <RiMicroscopeFill size={15} style={{ color: 'var(--brand)' }} />
                        <span style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>Variable Mapping</span>
                      </div>

                    {/* ── AI Variable Advisor Interactive Guide ── */}
                    <div className="rounded-xl p-3.5 transition-all shadow-sm"
                      style={{
                        background: advisorResult
                          ? 'linear-gradient(135deg, var(--surface-2), var(--surface-2))'
                          : 'var(--surface-2)',
                        border: advisorResult
                          ? '1px solid var(--border-2)'
                          : '1px solid var(--border)',
                      }}>
                      {/* Compact Header Bar */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 shadow-sm"
                            style={{ background: 'linear-gradient(135deg, var(--brand), #8b5cf6)', color: 'var(--brand-text)' }}>
                            <RiBrainFill size={15} />
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-xs font-bold" style={{ color: 'var(--text)' }}>AI Variable & Test Advisor</span>
                              <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.2 rounded-full"
                                style={{ background: 'color-mix(in srgb, var(--brand) 10%, transparent)', color: 'var(--brand)' }}>
                                Auto AI Guide
                              </span>
                            </div>
                            <p className="text-[11px] leading-tight text-ellipsis overflow-hidden mt-0.5" style={{ color: 'var(--text-3)' }}>
                              Unsure what variables to pick? The AI reads your research questions & hypotheses from Step 3 to recommend the exact Outcome and Predictor variables.
                            </p>
                          </div>
                        </div>

                        {/* Reduced, sleek compact button */}
                        <button
                          type="button"
                          onClick={handleVariableAdvisor}
                          disabled={advisorLoading}
                          className="btn shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all shadow-sm self-start sm:self-center"
                          style={{
                            background: 'var(--brand)',
                            color: 'var(--brand-text)',
                            border: '1px solid transparent',
                            opacity: advisorLoading ? 0.75 : 1,
                            fontSize: '11px',
                            height: '28px',
                          }}>
                          {advisorLoading ? (
                            <>
                              <RiLoader4Line size={13} className="animate-spin" />
                              <span>Analyzing...</span>
                            </>
                          ) : (
                            <>
                              <RiSparklingFill size={12} />
                              <span>{advisorResult ? 'Re-Analyze' : 'Auto AI: Recommend'}</span>
                            </>
                          )}
                        </button>
                      </div>

                      {/* Result Cards Display */}
                      {advisorResult && (
                        <div className="mt-3 pt-2.5 border-t space-y-2.5 animate-fadeIn" style={{ borderColor: 'color-mix(in srgb, var(--brand) 10%, transparent)' }}>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                            {/* DV Card */}
                            <div className="p-3 rounded-lg transition-all"
                              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1" style={{ color: 'var(--brand)' }}>
                                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--brand)' }} />
                                  Outcome Variable (DV)
                                </span>
                                <span className="text-[9px] font-semibold px-1.5 py-0.2 rounded-full"
                                  style={{ background: 'color-mix(in srgb, var(--brand) 10%, transparent)', color: 'var(--brand)' }}>
                                  {advisorResult.dependent_variable?.scale || 'Continuous'}
                                </span>
                              </div>
                              <p className="text-xs font-bold mb-0.5" style={{ color: 'var(--text)' }}>
                                {advisorResult.dependent_variable?.name || '(Not determined)'}
                              </p>
                              <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-2)' }}>
                                {advisorResult.dependent_variable?.why}
                              </p>
                            </div>

                            {/* IV Card */}
                            <div className="p-3 rounded-lg transition-all"
                              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1" style={{ color: 'var(--success)' }}>
                                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--success)' }} />
                                  Predictor / Grouping (IV)
                                </span>
                                <span className="text-[9px] font-semibold px-1.5 py-0.2 rounded-full"
                                  style={{ background: 'color-mix(in srgb, var(--success) 12%, transparent)', color: 'var(--success)' }}>
                                  {advisorResult.independent_variable?.scale || 'Nominal'}
                                  {advisorResult.independent_variable?.n_groups ? ` (${advisorResult.independent_variable.n_groups} grp)` : ''}
                                </span>
                              </div>
                              <p className="text-xs font-bold mb-0.5" style={{ color: 'var(--text)' }}>
                                {advisorResult.independent_variable?.name || '(Not determined)'}
                              </p>
                              <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-2)' }}>
                                {advisorResult.independent_variable?.why}
                              </p>
                            </div>
                          </div>

                          {/* Control / Mediating / Moderating Variable Cards */}
                          {(() => {
                            const ctrlVars: {name:string; why:string}[] = advisorResult.control_variables || [];
                            const medVars:  {name:string; why:string}[] = advisorResult.mediating_variables  || [];
                            const modVars:  {name:string; why:string}[] = advisorResult.moderating_variables || [];
                            const hasExtra = ctrlVars.length > 0 || medVars.length > 0 || modVars.length > 0;
                            if (!hasExtra) return null;
                            return (
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 mt-1">
                                {/* Control Variables */}
                                {ctrlVars.length > 0 && (
                                  <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                                    <span className="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 mb-1" style={{ color: '#f59e0b' }}>
                                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#f59e0b' }} />
                                      Control Variable(s)
                                    </span>
                                    {ctrlVars.map((v,i) => (
                                      <div key={i}>
                                        <p className="text-xs font-bold mb-0.5" style={{ color: 'var(--text)' }}>{v.name}</p>
                                        <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-2)' }}>{v.why}</p>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {/* Mediating Variables */}
                                {medVars.length > 0 && (
                                  <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                                    <span className="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 mb-1" style={{ color: '#8b5cf6' }}>
                                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#8b5cf6' }} />
                                      Mediating Variable(s)
                                    </span>
                                    {medVars.map((v,i) => (
                                      <div key={i}>
                                        <p className="text-xs font-bold mb-0.5" style={{ color: 'var(--text)' }}>{v.name}</p>
                                        <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-2)' }}>{v.why}</p>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {/* Moderating Variables */}
                                {modVars.length > 0 && (
                                  <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                                    <span className="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 mb-1" style={{ color: '#f97316' }}>
                                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#f97316' }} />
                                      Moderating Variable(s)
                                    </span>
                                    {modVars.map((v,i) => (
                                      <div key={i}>
                                        <p className="text-xs font-bold mb-0.5" style={{ color: 'var(--text)' }}>{v.name}</p>
                                        <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-2)' }}>{v.why}</p>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })()}

                          {/* Implied Test Card */}
                          {advisorResult.implied_test && (
                            <div className="p-2.5 rounded-lg flex items-start gap-2.5"
                              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                              <div className="w-5 h-5 rounded-md flex items-center justify-center shrink-0 mt-0.5"
                                style={{ background: 'color-mix(in srgb, var(--warning) 15%, transparent)', color: 'var(--warning)' }}>
                                <RiCpuFill size={12} />
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className="text-[11px] font-bold" style={{ color: 'var(--warning)' }}>
                                  Implied Golden Rule Test: {advisorResult.implied_test}
                                </span>
                                <p className="text-[11px] mt-0.5 leading-snug" style={{ color: 'var(--text-2)' }}>
                                  {advisorResult.implied_test_reason}
                                </p>
                              </div>
                            </div>
                          )}

                          {/* Action Footer */}
                          <div className="flex items-center justify-end pt-0.5">
                            <button
                              type="button"
                              onClick={handleApplyAdvisorVariables}
                              disabled={advisorApplied}
                              className="btn btn-sm shrink-0 flex items-center gap-1.5 px-3 py-1 text-[11px] font-semibold rounded-lg shadow-sm"
                              style={{
                                background: advisorApplied
                                  ? 'var(--surface-3)'
                                  : 'var(--brand)',
                                color: advisorApplied
                                  ? 'var(--success)'
                                  : 'var(--brand-text)',
                                border: advisorApplied
                                  ? '1px solid var(--border-2)'
                                  : '1px solid transparent',
                                height: '26px',
                                opacity: advisorApplied ? 0.9 : 1,
                              }}>
                              {advisorApplied ? (
                                <>
                                  <RiCheckboxCircleFill size={13} />
                                  <span>Applied to Form</span>
                                </>
                              ) : (
                                <>
                                  <RiAddFill size={13} />
                                  <span>Apply These Variables</span>
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    <Field label="Dependent Variable(s) — Outcome" error={touched ? stepErrors.dependent_variable : undefined}>

                      <MultiVarInput id="brief-dv" value={brief.dependent_variable}

                        onChange={v => update('dependent_variable', v)}

                        accentColor="var(--brand)"

                        errorBorder={!!(touched && stepErrors.dependent_variable)} />

                    </Field>

                    <Field label="Independent Variable(s) — Predictor / Grouping" error={touched ? stepErrors.independent_variable : undefined}>

                      <MultiVarInput id="brief-iv" value={brief.independent_variable}

                        onChange={v => update('independent_variable', v)}

                        accentColor="var(--success)"

                        errorBorder={!!(touched && stepErrors.independent_variable)} />

                    </Field>

                    <Field label="Control Variable(s)" required={false}>

                      <MultiVarInput id="brief-cv" value={brief.control_variable || ''}

                        onChange={v => update('control_variable', v)}

                        accentColor="#f59e0b" />

                    </Field>

                    <Field label="Mediating Variable(s)" required={false}>

                      <MultiVarInput id="brief-mv" value={brief.mediating_variable || ''}

                        onChange={v => update('mediating_variable', v)}

                        accentColor="#8b5cf6" />

                    </Field>

                    <Field label="Moderating Variable(s)" required={false}>

                      <MultiVarInput id="brief-modv" value={brief.moderating_variable || ''}

                        onChange={v => update('moderating_variable', v)}

                        accentColor="#f97316" />

                    </Field>

                    <Field label="Covariate Variable(s)" required={false}>

                      <MultiVarInput id="brief-cov" value={brief.covariate_variable || ''}

                        onChange={v => update('covariate_variable', v)}

                        accentColor="#06b6d4" />

                    </Field>

                    <Field label="Group Variable(s)" required={false}>

                      <MultiVarInput id="brief-grp" value={brief.group_variable || ''}

                        onChange={v => update('group_variable', v)}

                        accentColor="#84cc16" />

                    </Field>

                    <Field label="Exclude Variable(s)" required={false}>

                      <MultiVarInput id="brief-excl" value={brief.exclude_variable || ''}

                        onChange={v => update('exclude_variable', v)}

                        accentColor="#ef4444" />

                    </Field>

                    {dataDictionary && (

                      <AvailableColumnsPanel

                        dataDictionary={dataDictionary}

                        dvValue={brief.dependent_variable}

                        ivValue={brief.independent_variable}

                        cvValue={brief.control_variable || ''}

                        mvValue={brief.mediating_variable || ''}

                        modvValue={brief.moderating_variable || ''}

                        covValue={brief.covariate_variable || ''}

                        exclValue={brief.exclude_variable || ''}

                        grpValue={brief.group_variable || ''}

                        onAddDv={col => {
                          const cur = brief.dependent_variable ? brief.dependent_variable.split(',').map((v: string) => v.trim()).filter(Boolean) : [];
                          if (!cur.includes(col)) update('dependent_variable', [...cur, col].join(', '));
                        }}

                        onAddIv={col => {
                          const cur = brief.independent_variable ? brief.independent_variable.split(',').map((v: string) => v.trim()).filter(Boolean) : [];
                          if (!cur.includes(col)) update('independent_variable', [...cur, col].join(', '));
                        }}

                        onAddCv={col => {
                          const cur = (brief.control_variable || '').split(',').map((v: string) => v.trim()).filter(Boolean);
                          if (!cur.includes(col)) update('control_variable', [...cur, col].join(', '));
                        }}

                        onAddMv={col => {
                          const cur = (brief.mediating_variable || '').split(',').map((v: string) => v.trim()).filter(Boolean);
                          if (!cur.includes(col)) update('mediating_variable', [...cur, col].join(', '));
                        }}

                        onAddModv={col => {
                          const cur = (brief.moderating_variable || '').split(',').map((v: string) => v.trim()).filter(Boolean);
                          if (!cur.includes(col)) update('moderating_variable', [...cur, col].join(', '));
                        }}

                        onAddCov={col => {
                          const cur = (brief.covariate_variable || '').split(',').map((v: string) => v.trim()).filter(Boolean);
                          if (!cur.includes(col)) update('covariate_variable', [...cur, col].join(', '));
                        }}

                        onAddExcl={col => {
                          const cur = (brief.exclude_variable || '').split(',').map((v: string) => v.trim()).filter(Boolean);
                          if (!cur.includes(col)) update('exclude_variable', [...cur, col].join(', '));
                        }}

                        onAddGrp={col => {
                          const cur = (brief.group_variable || '').split(',').map((v: string) => v.trim()).filter(Boolean);
                          if (!cur.includes(col)) update('group_variable', [...cur, col].join(', '));
                        }}

                      />

                    )}



                    {/* ── Variable Scale Types — integrated with decoded data ── */}

                    {(() => {
                      // ── Helpers ──────────────────────────────────────────────
                      const toList = (v: string | undefined) =>
                        (v || '').split(',').map((s: string) => s.trim()).filter(Boolean);

                      const dvList   = toList(brief.dependent_variable);
                      const ivList   = toList(brief.independent_variable);
                      const cvList   = toList(brief.control_variable);
                      const mvList   = toList(brief.mediating_variable);
                      const modvList = toList(brief.moderating_variable);
                      const covList  = toList(brief.covariate_variable);
                      const exclList = toList(brief.exclude_variable);
                      const grpList  = toList(brief.group_variable);

                      // All explicitly named vars (from brief fields)
                      const namedVars: string[] = Array.from(new Set([
                        ...dvList, ...ivList, ...cvList, ...mvList, ...modvList,
                        ...covList, ...exclList, ...grpList,
                      ])).filter(Boolean);

                      // All decoded dataset columns
                      const decodedCols: string[] = dataDictionary ? Object.keys(dataDictionary) : [];

                      // Union: named vars + decoded cols (named first)
                      const allCols: string[] = Array.from(new Set([...namedVars, ...decodedCols])).filter(Boolean);

                      // Role for a column
                      const roleOf = (col: string): string | null => {
                        if (dvList.includes(col))   return 'DV';
                        if (ivList.includes(col))   return 'IV';
                        if (cvList.includes(col))   return 'CV';
                        if (mvList.includes(col))   return 'MV';
                        if (modvList.includes(col)) return 'MODV';
                        if (covList.includes(col))  return 'COV';
                        if (exclList.includes(col)) return 'EXCL';
                        if (grpList.includes(col))  return 'GRP';
                        return null;
                      };

                      const roleColor: Record<string, string> = {
                        DV: '#6366f1', IV: '#10b981', CV: '#f59e0b',
                        MV: '#8b5cf6', MODV: '#f97316',
                        COV: '#06b6d4', EXCL: '#ef4444', GRP: '#84cc16',
                      };
                      const roleLabel: Record<string, string> = {
                        DV: 'Dependent', IV: 'Independent', CV: 'Control',
                        MV: 'Mediating', MODV: 'Moderating',
                        COV: 'Covariate', EXCL: 'Exclude', GRP: 'Group',
                      };

                      // ── Auto-suggest scale from dataDictionary or name heuristics ──
                      const inferScale = (col: string): string => {
                        const info = dataDictionary?.[col];
                        const lv   = (info?.level || '').toLowerCase();
                        const dt   = (info?.dtype || '').toLowerCase();
                        const nu   = info?.n_unique ?? null;
                        const name = col.toLowerCase();

                        // Explicit level from decode
                        if (lv === 'ratio' || lv === 'continuous' || lv === 'numeric' || lv === 'scale') return 'ratio';
                        if (lv === 'interval') return 'interval';
                        if (lv === 'ordinal') {
                          // Distinguish Likert by name pattern or unique count
                          if (nu !== null && nu <= 7 && (name.includes('q') || name.includes('likert') || name.startsWith('q'))) {
                            return nu <= 5 ? 'likert_5' : 'likert_7';
                          }
                          return 'ordinal';
                        }
                        if (lv === 'nominal' || lv === 'categorical') {
                          if (nu !== null && nu <= 2) return 'binary';
                          return 'categorical';
                        }

                        // Name-based heuristics
                        if (/^(gender|sex)$/i.test(name)) return 'binary';
                        if (/^(age|years?|income|salary|score|gpa|duration|hours|count)/.test(name)) return 'ratio';
                        if (/(department|dept|profession|shift|hospital|site|region|type|category|group)/.test(name)) return 'categorical';
                        if (/(_score$|composite|index|total)/.test(name)) return 'ratio';
                        // Likert by prefix pattern: q9_, q10_, etc.
                        if (/^q\d+_/.test(name)) {
                          if (nu !== null && nu <= 5) return 'likert_5';
                          if (nu !== null && nu <= 7) return 'likert_7';
                          return 'likert_5'; // default survey item assumption
                        }
                        if (/(employ|contract|type|mode|model|level)/.test(name)) return 'categorical';

                        // Dtype fallback
                        if (dt.includes('int') || dt.includes('float')) {
                          if (nu !== null && nu <= 7) return nu <= 5 ? 'likert_5' : 'likert_7';
                          return 'ratio';
                        }
                        if (dt.includes('object') || dt.includes('str') || dt.includes('bool')) return 'categorical';

                        return ''; // no suggestion
                      };

                      const scaleOptions = [
                        { value: 'nominal',    label: 'Nominal',            hint: 'Categories, no order (e.g. Gender, Region)' },
                        { value: 'binary',     label: 'Binary',             hint: '0/1 or Yes/No' },
                        { value: 'categorical',label: 'Categorical',        hint: 'Multi-class unordered groups (e.g. Profession, Department)' },
                        { value: 'ordinal',    label: 'Ordinal',            hint: 'Ranked (e.g. Low / Med / High)' },
                        { value: 'likert_5',   label: 'Likert (1–5)',       hint: '5-point agreement scale' },
                        { value: 'likert_7',   label: 'Likert (1–7)',       hint: '7-point agreement scale' },
                        { value: 'interval',   label: 'Interval',           hint: 'Equal spacing, no true zero' },
                        { value: 'ratio',      label: 'Ratio / Continuous', hint: 'True zero (e.g. Age, Score, Income)' },
                      ];

                      const scaleLabel: Record<string, string> = Object.fromEntries(scaleOptions.map(o => [o.value, o.label]));
                      const scaleHint:  Record<string, string> = Object.fromEntries(scaleOptions.map(o => [o.value, o.hint]));

                      const manualCount   = allCols.filter((v: string) => !!brief.variable_scales?.[v]).length;
                      const totalCols     = allCols.length;

                      // Auto-suggest all: fill ALL columns (assigned and unassigned)
                      // Overwrites only empty slots; never removes a manually chosen scale.
                      const autoSuggestAll = () => {
                        const next = { ...(brief.variable_scales || {}) };
                        // Include every column — named (assigned) + decoded
                        const allTargets = Array.from(new Set([
                          ...dvList, ...ivList, ...cvList, ...mvList, ...modvList,
                          ...covList, ...exclList, ...grpList,
                          ...allCols,
                        ])).filter(Boolean);
                        allTargets.forEach((col: string) => {
                          // Always infer; only skip if user has already set a value
                          if (!next[col]) {
                            const s = inferScale(col);
                            if (s) next[col] = s;
                          }
                        });
                        update('variable_scales', next);
                      };

                      // Quick-assign role helpers (supports all 8 role types)
                      const roleField = (role: string) =>
                        role === 'DV'   ? 'dependent_variable'
                      : role === 'IV'   ? 'independent_variable'
                      : role === 'CV'   ? 'control_variable'
                      : role === 'MV'   ? 'mediating_variable'
                      : role === 'MODV' ? 'moderating_variable'
                      : role === 'COV'  ? 'covariate_variable'
                      : role === 'EXCL' ? 'exclude_variable'
                      : role === 'GRP'  ? 'group_variable'
                      : 'independent_variable';

                      const addToRole = (col: string, role: string) => {
                        const field = roleField(role);
                        const cur = toList(brief[field]);
                        if (!cur.includes(col)) update(field, [...cur, col].join(', '));
                      };

                      const removeFromRole = (col: string, role: string) => {
                        const field = roleField(role);
                        const cur = toList(brief[field]);
                        update(field, cur.filter((v: string) => v !== col).join(', '));
                      };

                      // Split cols into groups: assigned roles first, then unassigned
                      const assignedCols   = allCols.filter((c: string) => roleOf(c) !== null);
                      const unassignedCols = allCols.filter((c: string) => roleOf(c) === null);

                      const renderRow = (col: string) => {
                        const role     = roleOf(col);
                        const info     = dataDictionary?.[col];
                        const current  = brief.variable_scales?.[col] || '';
                        const suggested = inferScale(col);
                        const isSuggested = !current && !!suggested;
                        const displayVal  = current || suggested;

                        return (
                          <div key={col}
                            style={{
                              background: role ? `color-mix(in srgb, ${roleColor[role]} 7%, var(--surface-2))` : 'var(--surface-2)',
                              border: `1px solid ${role ? roleColor[role] + '44' : 'var(--border)'}`,
                              borderRadius: 10, padding: '8px 10px',
                              display: 'grid', gridTemplateColumns: '1fr auto', gap: 6,
                              alignItems: 'start',
                            }}
                          >
                            {/* Left: col name + decoded metadata + role badge */}
                            <div style={{ minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', fontFamily: 'monospace' }}>{col}</span>
                                {role && (
                                  <span style={{
                                    fontSize: 9, fontWeight: 800, padding: '1px 6px', borderRadius: 6,
                                    background: roleColor[role] + '22', color: roleColor[role], letterSpacing: '0.05em',
                                  }}>{role} — {roleLabel[role]}</span>
                                )}
                                {isSuggested && (
                                  <span style={{
                                    fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 5,
                                    background: 'rgba(245,158,11,0.12)', color: '#f59e0b',
                                  }}>suggested</span>
                                )}
                              </div>



                              {/* Quick role assign buttons (only for unassigned) */}
                              {!role && (
                                <div style={{ display: 'flex', gap: 4, marginTop: 5, flexWrap: 'wrap' }}>
                                  {(['DV','IV','CV','MV','MODV'] as const).map(r => (
                                    <button key={r} type="button"
                                      onClick={() => addToRole(col, r)}
                                      style={{
                                        fontSize: 9, fontWeight: 700, padding: '1px 7px', borderRadius: 5, cursor: 'pointer',
                                        background: roleColor[r] + '18', color: roleColor[r],
                                        border: `1px solid ${roleColor[r]}44`, transition: 'all 0.1s',
                                      }}
                                      title={`Assign as ${roleLabel[r]}`}
                                    >
                                      +{r}
                                    </button>
                                  ))}
                                </div>
                              )}

                              {/* Remove from role button */}
                              {role && (
                                <button type="button"
                                  onClick={() => removeFromRole(col, role)}
                                  style={{
                                    marginTop: 4, fontSize: 9, fontWeight: 600, padding: '1px 7px', borderRadius: 5,
                                    cursor: 'pointer', background: 'var(--surface)', color: 'var(--text-3)',
                                    border: '1px solid var(--border)',
                                  }}
                                >
                                  ✕ Remove from {role}
                                </button>
                              )}
                            </div>

                            {/* Right: scale type select */}
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
                              <select
                                value={current}
                                onChange={e => update('variable_scales', { ...brief.variable_scales, [col]: e.target.value })}
                                className="input"
                                style={{
                                  fontSize: 11, padding: '2px 6px', height: 28, width: 140,
                                  borderColor: current ? 'var(--brand)' : isSuggested ? '#f59e0b55' : 'var(--border)',
                                  background: current ? 'color-mix(in srgb, var(--brand) 6%, var(--surface))' : 'var(--surface)',
                                }}
                                title={current ? scaleHint[current] : isSuggested ? `Suggested: ${scaleHint[suggested] || suggested}` : 'Select scale type'}
                              >
                                <option value="">{isSuggested ? `≈ ${scaleLabel[suggested] || suggested}` : '— scale type —'}</option>
                                {scaleOptions.map(o => (
                                  <option key={o.value} value={o.value} title={o.hint}>{o.label}</option>
                                ))}
                              </select>
                              {/* Accept suggestion button */}
                              {isSuggested && (
                                <button type="button"
                                  onClick={() => update('variable_scales', { ...brief.variable_scales, [col]: suggested })}
                                  style={{
                                    fontSize: 9, fontWeight: 700, padding: '1px 7px', borderRadius: 5,
                                    background: 'rgba(245,158,11,0.12)', color: '#f59e0b',
                                    border: '1px solid rgba(245,158,11,0.25)', cursor: 'pointer',
                                  }}
                                  title="Accept suggested scale type"
                                >✓ Accept</button>
                              )}
                            </div>
                          </div>
                        );
                      };

                      return (
                        <div className="rounded-xl p-4 space-y-3"
                          style={{ background: 'color-mix(in srgb, var(--brand) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--brand) 18%, transparent)' }}>

                          {/* Header */}
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <RiBrainFill size={14} style={{ color: 'var(--brand)' }} />
                              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>Variable Scale Types</span>
                              <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20,
                                background: 'color-mix(in srgb, var(--brand) 10%, transparent)', color: 'var(--brand)' }}>
                                Prevents wrong tests
                              </span>
                              {manualCount > 0 && (
                                <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20,
                                  background: 'rgba(16,185,129,0.12)', color: 'var(--success)' }}>
                                  {manualCount}/{totalCols} set
                                </span>
                              )}
                            </div>

                            <div style={{ display: 'flex', gap: 6 }}>
                              {/* AI Suggest — only in manual mode */}
                              {scaleMode === 'manual' && totalCols > 0 && manualCount < totalCols && (
                                <button type="button"
                                  onClick={() => { handleScaleAdvisor().then(() => { setTimeout(() => handleApplyScaleAdvisor(true), 300); }); }}
                                  disabled={scaleAdvisorLoading}
                                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold shadow-sm"
                                  style={{ background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)', color: '#6366f1' }}
                                  title="Use AI to suggest scale types for empty variables">
                                  {scaleAdvisorLoading ? <RiLoader4Line size={12} className="animate-spin" /> : <RiBrainFill size={12} />}
                                  {scaleAdvisorLoading ? 'Analyzing...' : 'AI Suggest'}
                                </button>
                              )}


                              {/* AI Auto / Manual Mode toggle */}
                              <button type="button"
                                onClick={() => setScaleMode(m => m === 'auto' ? 'manual' : 'auto')}
                                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all hover:-translate-y-0.5 active:translate-y-0 shadow-sm"
                                style={{
                                  background: scaleMode === 'manual'
                                    ? 'linear-gradient(135deg, color-mix(in srgb, var(--brand) 10%, transparent), rgba(79,70,229,0.15))'
                                    : 'var(--surface)',
                                  border: `1px solid ${scaleMode === 'manual' ? 'color-mix(in srgb, var(--brand) 18%, transparent)' : 'var(--border)'}`,
                                  color: scaleMode === 'manual' ? 'var(--brand)' : 'var(--text-2)',
                                }}>
                                {scaleMode === 'manual' ? <RiBrainFill size={13} /> : <RiCpuFill size={13} />}
                                {scaleMode === 'manual' ? 'AI Auto' : 'Manual Mode'}
                              </button>
                            </div>
                          </div>

                          {/* AI Auto mode — live preview with AI suggestions */}
                          {scaleMode === 'auto' ? (
                            <div style={{
                              background: 'var(--surface-2)', borderRadius: 10, padding: '14px 16px',
                              border: '1px solid var(--border)',
                            }}>
                              {/* Not yet loaded — show trigger */}
                              {!scaleAdvisorResult && !scaleAdvisorLoading && (
                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                                  <div style={{
                                    width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                                    background: 'color-mix(in srgb, var(--brand) 12%, transparent)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                  }}>
                                    <RiBrainFill size={16} style={{ color: 'var(--brand)' }} />
                                  </div>
                                  <div style={{ flex: 1 }}>
                                    <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', margin: '0 0 4px' }}>
                                      AI Auto Scale Detection
                                    </p>
                                    <p style={{ fontSize: 11, color: 'var(--text-3)', lineHeight: 1.6, margin: '0 0 10px' }}>
                                      Click below to analyze your dataset columns and research context. AI will classify each variable
                                      and detect Likert construct groupings automatically.
                                    </p>
                                    <button type="button" onClick={handleScaleAdvisor}
                                      className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold shadow-sm transition-all hover:-translate-y-0.5"
                                      style={{ background: 'linear-gradient(135deg, var(--brand), #7c3aed)', color: '#fff', border: 'none' }}>
                                      <RiBrainFill size={13} /> Analyze Dataset with AI
                                    </button>
                                  </div>
                                </div>
                              )}

                              {/* Loading state */}
                              {scaleAdvisorLoading && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0' }}>
                                  <RiLoader4Line size={20} className="animate-spin" style={{ color: 'var(--brand)' }} />
                                  <div>
                                    <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                                      Analyzing columns...
                                    </p>
                                    <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '2px 0 0' }}>
                                      AI is classifying variable scale types and detecting constructs
                                    </p>
                                  </div>
                                </div>
                              )}

                              {/* Results loaded — show preview */}
                              {scaleAdvisorResult && !scaleAdvisorLoading && (() => {
                                const scales = scaleAdvisorResult.variable_scales || {};
                                const constructs = scaleAdvisorResult.likert_constructs || [];
                                const scaleEntries = Object.entries(scales);
                                const isAI = scaleAdvisorResult.source === 'ai';
                                return (
                                  <div className="space-y-3">
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <RiBrainFill size={14} style={{ color: 'var(--brand)' }} />
                                        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>
                                          {scaleEntries.length} variables classified
                                        </span>
                                        <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20,
                                          background: isAI ? 'rgba(99,102,241,0.12)' : 'rgba(245,158,11,0.12)',
                                          color: isAI ? '#6366f1' : '#f59e0b' }}>
                                          {isAI ? 'AI-powered' : 'Heuristic'}
                                        </span>
                                      </div>
                                      <div style={{ display: 'flex', gap: 6 }}>
                                        <button type="button" onClick={() => handleApplyScaleAdvisor(false)}
                                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold shadow-sm"
                                          style={{ background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.3)', color: '#10b981' }}>
                                          Accept All
                                        </button>
                                        <button type="button" onClick={handleScaleAdvisor}
                                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold shadow-sm"
                                          style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-2)' }}>
                                          Re-analyze
                                        </button>
                                      </div>
                                    </div>

                                    {/* Scale preview grid */}
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 6 }}>
                                      {scaleEntries.slice(0, 20).map(([col, info]: [string, any]) => {
                                        const scaleName = scaleLabel[info?.scale] || info?.scale || '?';
                                        const reason = info?.reason || '';
                                        const role = roleOf(col);
                                        return (
                                          <div key={col} style={{
                                            background: 'var(--surface)', borderRadius: 8, padding: '8px 10px',
                                            border: '1px solid var(--border)', fontSize: 11,
                                          }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
                                              {role && (
                                                <span style={{ fontSize: 9, fontWeight: 700, padding: '0 5px', borderRadius: 4,
                                                  background: `${roleColor[role]}20`, color: roleColor[role] }}>{role}</span>
                                              )}
                                              <span style={{ fontWeight: 600, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{col}</span>
                                            </div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--brand)', padding: '1px 6px', borderRadius: 4,
                                                background: 'color-mix(in srgb, var(--brand) 10%, transparent)' }}>{scaleName}</span>
                                            </div>
                                            {reason && (
                                              <p style={{ fontSize: 9, color: 'var(--text-3)', margin: '3px 0 0', lineHeight: 1.4 }}>{reason}</p>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                    {scaleEntries.length > 20 && (
                                      <p style={{ fontSize: 10, color: 'var(--text-3)', margin: 0 }}>
                                        + {scaleEntries.length - 20} more variables (switch to Manual Mode to view all)
                                      </p>
                                    )}

                                    {/* Constructs preview */}
                                    {constructs.length > 0 && (
                                      <div style={{ marginTop: 8 }}>
                                        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text)', margin: '0 0 6px' }}>
                                          Detected Constructs ({constructs.length})
                                        </p>
                                        {constructs.map((c: any, i: number) => (
                                          <div key={i} style={{
                                            background: 'rgba(16,185,129,0.06)', borderRadius: 8, padding: '8px 10px',
                                            border: '1px solid rgba(16,185,129,0.15)', marginBottom: 4,
                                          }}>
                                            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--success)' }}>{c.name}</span>
                                            <span style={{ fontSize: 10, color: 'var(--text-3)', marginLeft: 6 }}>({(c.columns || []).length} items)</span>
                                            {c.reason && <p style={{ fontSize: 9, color: 'var(--text-3)', margin: '2px 0 0' }}>{c.reason}</p>}
                                          </div>
                                        ))}
                                      </div>
                                    )}

                                    <p style={{ fontSize: 10, color: 'var(--text-3)', margin: '6px 0 0', fontStyle: 'italic' }}>
                                      Click <strong>Accept All</strong> to apply these scales, or switch to <strong>Manual Mode</strong> to override individual variables.
                                    </p>
                                  </div>
                                );
                              })()}
                            </div>
                          ) : (
                            /* Manual Mode — show per-variable dropdowns */
                            <div className="space-y-3 animate-slide-up">
                              <p style={{ fontSize: 11, color: 'var(--text-3)', margin: 0, lineHeight: 1.5 }}>
                                Select a scale type for each variable. Assigned variables (DV, IV, etc.) appear first.
                                Leave blank to let AI Auto fill the rest.
                              </p>
                              {totalCols === 0 ? (
                                <p style={{ fontSize: 11, color: 'var(--text-3)', margin: 0 }}>
                                  Add variable names in the DV/IV fields above or upload a dataset to see all columns here.
                                </p>
                              ) : (
                                <>
                                  {/* Assigned variables group */}
                                  {assignedCols.length > 0 && (
                                    <div className="space-y-1.5">
                                      <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
                                        ✦ Assigned Variables ({assignedCols.length})
                                      </p>
                                      {assignedCols.map((col: string) => renderRow(col))}
                                    </div>
                                  )}

                                  {/* Unassigned dataset columns */}
                                  {unassignedCols.length > 0 && (
                                    <div className="space-y-1.5">
                                      <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
                                        ○ Other Dataset Columns ({unassignedCols.length}) — click +DV/+IV/+CV/+MV/+MODV to assign
                                      </p>
                                      {unassignedCols.map((col: string) => renderRow(col))}
                                    </div>
                                  )}
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })()}




                    {/* ── Measurement Scales / Constructs ── */}


                    {(() => {

                      const constructs: Array<{ name: string; columns: string[] }> = brief.likert_constructs || [];

                      const datasetCols: string[] = dataDictionary ? Object.keys(dataDictionary) : [];

                      const briefVars: string[] = [

                        brief.dependent_variable, brief.independent_variable,

                        brief.control_variable, brief.mediating_variable, brief.moderating_variable,

                      ]

                        .filter(Boolean)

                        .flatMap((v: string) => v.split(',').map((s: string) => s.trim()))

                        .filter(Boolean);

                      const allCols: string[] = Array.from(new Set([...datasetCols, ...briefVars]));



                      const addConstruct = () => update('likert_constructs', [...constructs, { name: '', columns: [] }]);

                      const removeConstruct = (i: number) => update('likert_constructs', constructs.filter((_: any, idx: number) => idx !== i));

                      const updateConstruct = (i: number, patch: Partial<{ name: string; columns: string[] }>) =>

                        update('likert_constructs', constructs.map((c: any, idx: number) => idx === i ? { ...c, ...patch } : c));

                      const addColumn = (i: number, col: string) => {

                        const cur = constructs[i]?.columns || [];

                        if (!cur.includes(col)) updateConstruct(i, { columns: [...cur, col] });

                      };

                      const removeColumn = (i: number, col: string) =>

                        updateConstruct(i, { columns: (constructs[i]?.columns || []).filter((c: string) => c !== col) });



                      return (

                        <div className="rounded-xl p-4 space-y-3"

                          style={{ background: 'color-mix(in srgb, var(--success) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--success) 12%, transparent)' }}>

                          <div className="flex items-center justify-between">

                            <div className="flex items-center gap-2">

                              <RiStackFill size={14} style={{ color: 'var(--success)' }} />

                              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>Measurement Scales / Constructs</span>

                              <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20,

                                background: 'color-mix(in srgb, var(--success) 12%, transparent)', color: 'var(--success)' }}>

                                Groups Likert items

                              </span>

                            </div>

                            <button

                              type="button"

                              onClick={() => setConstructMode(m => m === 'auto' ? 'manual' : 'auto')}

                              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all hover:-translate-y-0.5 active:translate-y-0 shadow-sm"

                              style={{ 

                                background: constructMode === 'auto' ? 'var(--surface)' : 'linear-gradient(135deg, color-mix(in srgb, var(--success) 12%, transparent), rgba(5,150,105,0.15))', 

                                border: `1px solid ${constructMode === 'auto' ? 'var(--border)' : 'color-mix(in srgb, var(--success) 30%, transparent)'}`, 

                                color: constructMode === 'auto' ? 'var(--text-2)' : 'var(--success)' 

                              }}>

                              {constructMode === 'auto' ? <RiCpuFill size={13} /> : <RiBrainFill size={13} />} 

                              {constructMode === 'auto' ? 'Manual Selection' : 'Auto AI'}

                            </button>

                          </div>



                          {constructMode === 'auto' ? (

                            <div className="space-y-1">

                              <p style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.5, margin: 0 }}>

                                AI auto will detect which columns belong together (e.g. LS1–LS5 → Leadership Scale) and run Cronbach's Alpha per group automatically.

                              </p>

                              {constructs.length > 0 && (

                                <p style={{ fontSize: 11, color: 'var(--success)', margin: '4px 0 0', fontWeight: 600 }}>

                                  ✓ {constructs.length} named construct{constructs.length > 1 ? 's' : ''} defined — AI auto will group the rest

                                </p>

                              )}

                            </div>

                          ) : (

                            <div className="space-y-2 animate-slide-up">

                              <p style={{ fontSize: 11, color: 'var(--text-3)' }}>Define Likert construct groups and assign variables:</p>

                              {constructs.length === 0 && (

                                <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '0 0 6px' }}>

                                  No custom constructs defined yet. Click "+ Add Construct / Scale" below.

                                </p>

                              )}



                              {constructs.map((c: { name: string; columns: string[] }, i: number) => (

                                <div key={i} className="p-3 rounded-xl space-y-2" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>

                                  <div className="flex items-center gap-2">

                                    <span className="w-5 h-5 rounded-md flex items-center justify-center text-xs font-bold shrink-0"

                                      style={{ background: 'color-mix(in srgb, var(--success) 12%, transparent)', color: 'var(--success)' }}>{i + 1}</span>

                                    <input

                                      className="input flex-1"

                                      placeholder="Scale / Construct name (e.g. Job Satisfaction Scale)"

                                      value={c.name}

                                      onChange={e => updateConstruct(i, { name: e.target.value })}

                                      style={{ fontSize: 12, height: 30 }}

                                    />

                                    <button type="button" onClick={() => removeConstruct(i)} className="btn btn-ghost btn-icon" style={{ color: 'var(--text-3)' }}>

                                      <RiCloseFill size={14} />

                                    </button>

                                  </div>



                                  {/* Column pills */}

                                  <div className="flex flex-wrap gap-1.5">

                                    {(c.columns || []).map((col: string) => (

                                      <span key={col} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 6, background: 'color-mix(in srgb, var(--success) 12%, transparent)', fontSize: 11, color: 'var(--success)', fontWeight: 600 }}>

                                        {col}

                                        <button type="button" onClick={() => removeColumn(i, col)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', fontSize: 11, padding: 0, lineHeight: 1 }}>✕</button>

                                      </span>

                                    ))}

                                    {(c.columns || []).length === 0 && <span style={{ fontSize: 10, color: 'var(--text-3)' }}>No columns added yet</span>}

                                  </div>



                                  {/* Column picker dropdown */}

                                  {allCols.length > 0 && (

                                    <select

                                      className="input"

                                      value=""

                                      onChange={e => { if (e.target.value) addColumn(i, e.target.value); }}

                                      style={{ fontSize: 11, padding: '4px 8px', height: 30, width: '100%' }}

                                    >

                                      <option value="">+ Add column from dataset…</option>

                                      {allCols.filter((col: string) => !(c.columns || []).includes(col)).map((col: string) => (

                                        <option key={col} value={col}>{col}</option>

                                      ))}

                                    </select>

                                  )}

                                  {allCols.length === 0 && (

                                    <p style={{ fontSize: 10, color: 'var(--text-3)', margin: 0 }}>

                                      Add variable names above (DV / IV fields) or upload a dataset to pick columns.

                                    </p>

                                  )}

                                </div>

                              ))}



                              <button

                                type="button"

                                onClick={addConstruct}

                                style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--success)', background: 'color-mix(in srgb, var(--success) 12%, transparent)', border: '1.5px dashed color-mix(in srgb, var(--success) 12%, transparent)', borderRadius: 8, padding: '6px 12px', cursor: 'pointer' }}

                              >

                                + Add Construct / Scale

                              </button>

                            </div>

                          )}

                        </div>

                      );

                    })()}



                  </div>

                )}



                {/* ── Step 5: Statistical Techniques ── */}

                {currentStep === 5 && (

                  <div className="space-y-4 wizard-step-content">

                    <div className="flex items-center gap-2 mb-1">

                      <RiCpuFill size={15} style={{ color: 'var(--brand)' }} />

                      <span style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>Statistical Techniques</span>

                    </div>

                    <TechniqueSelector

                      autoSelect={autoSelect}

                      setAutoSelect={setAutoSelect}

                      selected={selectedTechniques}

                      setSelected={setSelectedTechniques}

                      dataDictionary={dataDictionary}

                      brief={brief}

                      studyTypes={studyTypes}

                    />

                  </div>

                )}



                {/* ── Step 6: Output & Submission ── */}

                {currentStep === 6 && (

                  <div className="space-y-5 wizard-step-content">

                    <div className="flex items-center gap-2 mb-1">

                      <RiFileTextFill size={15} style={{ color: 'var(--brand)' }} />

                      <span style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>Output Format & Submission</span>

                    </div>



                    <div className="grid grid-cols-2 gap-3">

                      {REPORT_TYPES.map(rt => {

                        const Icon = rt.icon;

                        const active = reportType === rt.value;

                        return (

                          <button key={rt.value} onClick={() => { setReportType(rt.value); if (rt.value !== 'chapter4') setAcademicTradition('standard'); }}

                            className="rounded-xl p-3.5 text-left transition-all duration-150"

                            style={{ background: active ? `${rt.color}14` : 'var(--surface-2)', border: `1.5px solid ${active ? rt.color + '50' : 'var(--border)'}`, boxShadow: active ? `0 0 0 3px ${rt.color}15` : 'none' }}>

                            <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-2" style={{ background: active ? rt.color + '22' : 'var(--surface)' }}>

                              <Icon size={17} style={{ color: active ? rt.color : 'var(--text-3)' }} />

                            </div>

                            <p style={{ fontSize: 12, fontWeight: 700, color: active ? 'var(--text)' : 'var(--text-2)', margin: 0 }}>{rt.label}</p>

                            <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '2px 0 0' }}>{rt.sub}</p>

                          </button>

                        );

                      })}

                    </div>

                    {reportType === 'chapter4' && (

                      <div className="space-y-2">

                        <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-2)' }}>Dissertation Format</p>

                        <div className="grid grid-cols-2 gap-2">

                          {[{ value: 'standard', label: 'Global (Default)' }, { value: 'nigerian', label: 'Nigerian University' }, { value: 'uk', label: 'British Academic' }, { value: 'apa', label: 'APA 7th Edition' }].map(t => (

                            <button key={t.value} onClick={() => setAcademicTradition(t.value)}

                              className="px-3 py-2 rounded-lg text-xs font-semibold transition-all text-left"

                              style={{ background: academicTradition === t.value ? 'color-mix(in srgb, var(--brand) 10%, transparent)' : 'var(--surface-2)', border: `1.5px solid ${academicTradition === t.value ? 'var(--brand)' : 'var(--border)'}`, color: academicTradition === t.value ? 'var(--brand)' : 'var(--text-2)' }}>

                              {t.label}

                            </button>

                          ))}

                        </div>

                      </div>

                    )}



                    {/* Visualizations */}

                    <div className="rounded-xl p-4 space-y-3"

                      style={{ background: 'rgba(99,102,241,0.04)', border: '1px solid var(--border)' }}>

                      <div className="flex items-center justify-between">

                        <div className="flex items-center gap-2">

                          <RiBarChartFill size={14} style={{ color: 'var(--brand)' }} />

                          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>Visualization Types</span>

                        </div>

                        <button onClick={() => setAutoViz(v => !v)}

                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all hover:-translate-y-0.5 active:translate-y-0 shadow-sm"

                          style={{ 

                            background: autoViz ? 'var(--surface)' : 'linear-gradient(135deg, rgba(99,102,241,0.1), rgba(79,70,229,0.15))', 

                            border: `1px solid ${autoViz ? 'var(--border)' : 'rgba(99,102,241,0.3)'}`, 

                            color: autoViz ? 'var(--text-2)' : 'var(--brand)' 

                          }}>

                          {autoViz ? <RiCpuFill size={13} /> : <RiBrainFill size={13} />} 

                          {autoViz ? 'Manual Selection' : 'AI Auto-Select'}

                        </button>

                      </div>

                      {autoViz ? (

                        <p style={{ fontSize: 12, color: 'var(--text-3)' }}>The AI will choose the most appropriate chart types for each test result.</p>

                      ) : (

                        <div className="grid grid-cols-3 gap-2">

                          {[

                            { id: 'bar',       label: 'Bar Charts',     Icon: RiBarChartFill},

                            { id: 'pie',       label: 'Pie Charts',     Icon: RiPieChartFill},

                            { id: 'histogram', label: 'Histograms',     Icon: RiBarChart2Fill},

                            { id: 'box',       label: 'Box Plots',      Icon: RiDragDropFill},

                            { id: 'scatter',   label: 'Scatter Plots',  Icon: RiBubbleChartFill},

                            { id: 'line',      label: 'Line Charts',    Icon: RiLineChartFill},

                            { id: 'heatmap',   label: 'Heatmaps',       Icon: RiStackFill},

                            { id: 'violin',    label: 'Violin Plots',   Icon: RiPulseFill},

                            { id: 'wordcloud', label: 'Word Cloud',     Icon: RiHashtag},

                            { id: 'forest',    label: 'Forest Plot',    Icon: RiMapFill},

                            { id: 'funnel',    label: 'Funnel Chart',   Icon: RiLineChartFill},

                            { id: 'frequency', label: 'Freq. Tables',   Icon: RiClipboardFill},

                          ].map(({ id, label, Icon }) => {

                            const active = selectedViz.has(id);

                            return (

                              <button key={id} onClick={() => toggleViz(id)}

                                className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition-all"

                                style={{ background: active ? 'color-mix(in srgb, var(--brand) 10%, transparent)' : 'var(--surface-2)', border: `1.5px solid ${active ? 'var(--brand)' : 'var(--border)'}`, color: active ? 'var(--brand)' : 'var(--text-2)' }}>

                                <Icon size={12} style={{ flexShrink: 0 }} />

                                <span style={{ lineHeight: 1.2 }}>{label}</span>

                                {active && <RiCheckboxCircleFill size={11} style={{ marginLeft: 'auto', flexShrink: 0 }} />}

                              </button>

                            );

                          })}

                        </div>

                      )}

                      {!autoViz && selectedViz.size === 0 && (

                        <p className="text-xs flex items-center gap-1" style={{ color: 'var(--warning)' }}><RiAlertFill size={12} /> Select at least one chart type, or switch to AI Auto-Select</p>

                      )}

                    </div>



                    {/* ── Table Selection ── */}

                    <div className="rounded-xl p-4 space-y-3"

                      style={{ background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.18)' }}>

                      <div className="flex items-center justify-between">

                        <div className="flex items-center gap-2">

                          <RiClipboardFill size={14} style={{ color: 'var(--success)' }} />

                          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>Result Tables</span>

                          <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20,

                            background: 'color-mix(in srgb, var(--success) 12%, transparent)', color: 'var(--success)' }}>Included in report</span>

                        </div>

                        <button onClick={() => setAutoTables(v => !v)}

                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all hover:-translate-y-0.5 active:translate-y-0 shadow-sm"

                          style={{

                            background: autoTables ? 'var(--surface)' : 'linear-gradient(135deg, rgba(16,185,129,0.1), rgba(5,150,105,0.15))',

                            border: `1px solid ${autoTables ? 'var(--border)' : 'color-mix(in srgb, var(--success) 30%, transparent)'}`,

                            color: autoTables ? 'var(--text-2)' : 'var(--success)',

                          }}>

                          {autoTables ? <RiCpuFill size={13} /> : <RiBrainFill size={13} />}

                          {autoTables ? 'Manual Selection' : 'AI Auto-Generate'}

                        </button>

                      </div>



                      {autoTables ? (

                        <p style={{ fontSize: 12, color: 'var(--text-3)' }}>

                          The AI will automatically include all relevant result tables based on your chosen statistical tests.

                        </p>

                      ) : (

                        <div className="space-y-2 animate-slide-up">

                          <p style={{ fontSize: 11, color: 'var(--text-3)' }}>Select the tables to include in your report:</p>

                          <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 gap-2">

                            {TABLE_TYPES.map(({ id, label, icon: Icon, color }) => {

                              const active = selectedTables.has(id);

                              return (

                                <button key={id} onClick={() => toggleTable(id)}

                                  className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition-all text-left"

                                  style={{

                                    background: active ? 'color-mix(in srgb, var(--success) 12%, transparent)' : 'var(--surface-2)',

                                    border: `1.5px solid ${active ? 'var(--success)' : 'var(--border)'}`,

                                    color: active ? 'var(--success)' : 'var(--text-2)',

                                  }}>

                                  <Icon size={12} style={{ color: active ? 'var(--success)' : color, flexShrink: 0 }} />

                                  <span style={{ lineHeight: 1.2 }}>{label}</span>

                                  {active && <RiCheckboxCircleFill size={11} style={{ marginLeft: 'auto', flexShrink: 0 }} />}

                                </button>

                              );

                            })}

                          </div>

                          {!autoTables && selectedTables.size === 0 && (

                            <p className="text-xs flex items-center gap-1" style={{ color: 'var(--warning)' }}>

                              <RiAlertFill size={12} /> Select at least one table, or switch to AI Auto-Generate

                            </p>

                          )}

                        </div>

                      )}

                    </div>



                    {/* Supporting document */}

                    <div style={{ borderTop: '1px solid var(--border)', paddingTop: 20, marginTop: 12 }}>

                      <div className="flex items-center gap-2 mb-3">

                        <RiBookOpenFill size={18} style={{ color: 'var(--success)' }} />

                        <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', margin: 0 }}>

                          Supporting Document <span style={{ color: 'var(--success)', fontWeight: 600, fontSize: 12, marginLeft: 4 }}>(Optional)</span>

                        </h3>

                      </div>

                      <p style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 16, lineHeight: 1.5 }}>

                        Upload prior chapter 1-3, reports, background documents, methodology notes, or any relevant context to generate a highly personalised analysis report/chapter 4.

                      </p>

                      

                      {chaptersDoc ? (

                        <div className="flex items-center gap-3 px-4 py-3 rounded-xl transition-all" style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid color-mix(in srgb, var(--success) 30%, transparent)' }}>

                          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(16,185,129,0.2)' }}>

                            <RiFileTextFill size={20} style={{ color: 'var(--success)' }} />

                          </div>

                          <div className="flex-1 min-w-0">

                            <p className="text-sm font-bold truncate" style={{ color: 'var(--text)' }}>{chaptersDoc.name}</p>

                            <p className="text-xs font-medium" style={{ color: 'var(--success)' }}>{(chaptersDoc.size / 1024).toFixed(0)} KB • Ready to include</p>

                          </div>

                          <button className="btn btn-ghost btn-icon hover:bg-red-500/10" style={{ color: 'var(--text-2)' }} onClick={() => setChaptersDoc(null)} title="Remove file">

                            <RiCloseFill size={16} />

                          </button>

                        </div>

                      ) : (

                        <label className="flex flex-col items-center justify-center gap-3 px-6 py-6 rounded-2xl cursor-pointer transition-all group"

                          style={{ background: 'var(--surface-2)', border: '2px dashed var(--border)' }}

                          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--success)'; e.currentTarget.style.background = 'rgba(16,185,129,0.02)' }}

                          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--surface-2)' }}>

                          <div className="w-12 h-12 rounded-full flex items-center justify-center transition-all group-hover:scale-110" style={{ background: 'rgba(16,185,129,0.1)' }}>

                            <RiUpload2Fill size={20} style={{ color: 'var(--success)' }} />

                          </div>

                          <div className="text-center">

                            <span className="block text-sm font-bold mb-1" style={{ color: 'var(--text)' }}>Click to upload file</span>

                            <span className="block text-xs" style={{ color: 'var(--text-3)' }}>Accepts .docx, .pdf, or .txt</span>

                          </div>

                          <input type="file" className="hidden" accept=".docx,.pdf,.txt"

                            onChange={e => { const f = e.target.files?.[0]; if (f) setChaptersDoc(f); e.target.value = ''; }} />

                        </label>

                      )}

                    </div>



                    {/* Brief summary */}

                    <div className="rounded-xl p-4 space-y-2 mt-2" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>

                      <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--brand)' }}>Final Confirmation</p>

                      {[

                        { label: 'File',        value: dataFile?.name },

                        { label: 'Topic',       value: brief.topic },

                        { label: 'Study Types', value: studyTypes.map((t: string) => t.charAt(0).toUpperCase() + t.slice(1)).join(', ') },

                        { label: 'Sample (n)',  value: sampleSize ? `n = ${sampleSize}` : undefined },

                        { label: brief.dependent_variable.includes(',') ? 'DVs' : 'DV', value: brief.dependent_variable },

                        { label: brief.independent_variable.includes(',') ? 'IVs' : 'IV', value: brief.independent_variable },

                        ...(brief.control_variable ? [{ label: brief.control_variable.includes(',') ? 'Controls' : 'Control', value: brief.control_variable }] : []),

                        ...(brief.mediating_variable ? [{ label: 'Mediator', value: brief.mediating_variable }] : []),

                        ...(brief.moderating_variable ? [{ label: 'Moderator', value: brief.moderating_variable }] : []),

                        ...(brief.nesting_variable ? [{ label: brief.nesting_variable.includes(',') ? 'Nesting' : 'Nesting', value: brief.nesting_variable }] : []),

                        { label: 'Techniques',  value: autoSelect ? 'AI Auto-Select' : `${selectedTechniques.size} selected manually` },

                        { label: 'Qual. Files', value: hasQualitative && qualFiles.length > 0 ? `${qualFiles.length} transcript${qualFiles.length > 1 ? 's' : ''} uploaded` : undefined },

                        { label: 'Viz',         value: autoViz ? 'AI picks charts' : `${selectedViz.size} chart type${selectedViz.size !== 1 ? 's' : ''} selected` },

                        { label: 'Tables',      value: autoTables ? 'AI auto-generates all' : selectedTables.size > 0 ? `${selectedTables.size} table${selectedTables.size !== 1 ? 's' : ''} selected` : 'None selected' },

                        { label: 'Format',      value: REPORT_TYPES.find(r => r.value === reportType)?.label },

                      ].map(({ label, value }) => value ? (

                        <div key={label} className="flex gap-2">

                          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', minWidth: 80 }}>{label}</span>

                          <span style={{ fontSize: 12, color: 'var(--text-2)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</span>

                        </div>

                      ) : null)}

                    </div>

                  </div>

                )}



                {currentStep >= 5 && (

                  <div className="mt-4">

                    <AnalysisCostBanner estimate={creditEstimate} loading={estimateLoading} />

                  </div>

                )}

              </div>



              {/* ── STICKY BOTTOM NAVIGATION BAR ── */}

              <div

                style={{

                  position: 'sticky',

                  bottom: 0,

                  background: 'var(--surface)',

                  borderTop: '1px solid var(--border)',

                  padding: '14px 28px',

                  display: 'flex',

                  alignItems: 'center',

                  justifyContent: 'space-between',

                  gap: 12,

                  zIndex: 10,

                  backdropFilter: 'blur(12px)',

                  marginTop: 20,

                }}

              >

                {/* Back */}

                <button

                  onClick={goPrev}

                  className="step-nav-btn"

                  style={{

                    visibility: currentStep === 1 ? 'hidden' : 'visible',

                    display: 'flex', alignItems: 'center', gap: 8,

                    padding: '9px 18px', borderRadius: 10, border: '1px solid var(--border)',

                    background: 'var(--surface-2)', color: 'var(--text-2)',

                    fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',

                  }}

                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--brand)'; e.currentTarget.style.color = 'var(--brand)'; }}

                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-2)'; }}

                >

                  <RiArrowLeftFill size={15} /> Back

                </button>



                {/* Step dots */}

                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>

                  {STEPS.map(s => (

                    <div key={s.id} style={{

                      width: currentStep === s.id ? 20 : 6,

                      height: 6,

                      borderRadius: 3,

                      background: s.id < currentStep ? 'var(--success)' : currentStep === s.id ? 'var(--brand)' : 'var(--border)',

                      transition: 'all 0.3s ease',

                    }} />

                  ))}

                </div>



                {/* Next / Run */}

                {currentStep < STEPS.length ? (

                  <button

                    onClick={goNext}

                    style={{

                      display: 'flex', alignItems: 'center', gap: 8,

                      padding: '9px 22px', borderRadius: 10,

                      background: 'var(--text)',

                      color: 'var(--bg)', border: 'none',

                      fontSize: 13, fontWeight: 700, cursor: 'pointer',

                      boxShadow: '0 4px 14px rgba(0,0,0,0.1)',

                      transition: 'all 0.15s',

                    }}

                    onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 6px 20px rgba(0,0,0,0.15)'; }}

                    onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '0 4px 14px rgba(0,0,0,0.1)'; }}

                  >

                    Continue <RiArrowRightSFill size={16} />

                  </button>

                ) : (

                  <button

                    onClick={handleRunAnalysis}

                    disabled={uploading}

                    style={{

                      display: 'flex', alignItems: 'center', gap: 8,

                      padding: '9px 22px', borderRadius: 10,

                      background: uploading ? 'var(--surface-2)' : 'var(--text)',

                      color: uploading ? 'var(--text-3)' : 'var(--bg)', border: 'none',

                      fontSize: 13, fontWeight: 700, cursor: uploading ? 'not-allowed' : 'pointer',

                      boxShadow: uploading ? 'none' : '0 4px 14px rgba(0,0,0,0.1)',

                      transition: 'all 0.15s',

                    }}

                  >

                    {uploading ? <RiLoader4Line size={15} className="animate-spin" /> : <RiFlaskFill size={15} />}

                    Run Analysis

                  </button>

                )}

              </div>

            </div>

          </div>



          {/* ============================================================

              RIGHT: Your Analyses

          ============================================================ */}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>



            {/* Header row */}

            <div style={{

              display: 'flex', alignItems: 'center', justifyContent: 'space-between',

              padding: '0 2px',

            }}>

              <div>

                <h2 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 800, fontSize: '1.05rem', color: 'var(--text)', margin: 0, letterSpacing: '-0.01em' }}>

                  Your Analyses

                </h2>

                <p style={{ fontSize: 12, color: 'var(--text-3)', margin: '2px 0 0' }}>

                  {jobs.length} total job{jobs.length !== 1 ? 's' : ''}

                </p>

              </div>

              <button

                type="button"

                onClick={() => mutateJobs()}

                style={{

                  display: 'flex', alignItems: 'center', gap: 6,

                  padding: '7px 14px', borderRadius: 10,

                  background: 'var(--surface-2)', border: '1px solid var(--border)',

                  color: 'var(--text-2)', fontSize: 12, fontWeight: 600, cursor: 'pointer',

                  transition: 'all 0.15s',

                }}

                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--brand)'; e.currentTarget.style.color = 'var(--brand)'; }}

                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-2)'; }}

              >

                <RiRefreshLine size={13} /> Refresh

              </button>

            </div>



            {/* Jobs list */}

            {loading ? (

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

                {[1, 2, 3].map(i => (

                  <div key={i} style={{

                    height: 88, borderRadius: 16, background: 'var(--surface-2)',

                    border: '1px solid var(--border)',

                    overflow: 'hidden', position: 'relative',

                  }}>

                    <div style={{

                      position: 'absolute', inset: 0,

                      background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.06) 50%, transparent 100%)',

                      animation: 'shimmerBar 1.6s ease-in-out infinite',

                    }} />

                  </div>

                ))}

              </div>

            ) : jobs.length === 0 ? (

              <div style={{

                borderRadius: 20, padding: '48px 24px',

                background: 'var(--surface)', border: '1px dashed var(--border)',

                display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 12,

              }}>

                <div style={{

                  width: 56, height: 56, borderRadius: 16,

                  background: 'rgba(99,102,241,0.08)', border: '1px solid var(--border)',

                  display: 'flex', alignItems: 'center', justifyContent: 'center',

                  animation: 'floatPulse 3s ease-in-out infinite',

                }}>

                  <RiBarChart2Fill size={26} style={{ color: 'var(--brand)' }} />

                </div>

                <h3 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: '0.95rem', color: 'var(--text)', margin: 0 }}>No analyses yet</h3>

                <p style={{ fontSize: 12, color: 'var(--text-2)', maxWidth: 220, lineHeight: 1.5 }}>Complete the brief on the left to start your first analysis pipeline.</p>

              </div>

            ) : (

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

                {jobs.slice(0, 6).map((job: any) => {

                  const status = STATUS_MAP[job.status] || STATUS_MAP.pending;

                  const isRunning = !['complete', 'failed', 'decode_review', 'awaiting_preprocessing_choice'].includes(job.status);

                  const isComplete = job.status === 'complete';

                  const isFailed = job.status === 'failed';

                  const isReview = job.status === 'decode_review' || job.status === 'awaiting_preprocessing_choice';

                  const accentColor = isComplete ? '#10b981' : isFailed ? '#ef4444' : isReview ? '#f59e0b' : '#6366f1';

                  return (

                    <Link key={job.id} href={`/analysis/${job.id}`} style={{ textDecoration: 'none' }}>

                      <div

                        className="job-card"

                        style={{

                          position: 'relative',

                          borderRadius: 16,

                          overflow: 'hidden',

                          background: 'var(--surface)',

                          border: `1px solid ${isComplete ? 'rgba(16,185,129,0.25)' : isFailed ? 'rgba(239,68,68,0.2)' : isReview ? 'rgba(245,158,11,0.25)' : 'var(--border)'}`,

                          padding: '14px 16px 14px 20px',

                        }}

                      >

                        {/* Left color accent strip */}

                        <div style={{

                          position: 'absolute', left: 0, top: 0, bottom: 0, width: 4,

                          background: `linear-gradient(180deg, ${accentColor}, ${accentColor}99)`,

                          borderRadius: '16px 0 0 16px',

                        }} />



                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>

                          <div style={{ flex: 1, minWidth: 0 }}>

                            <h4 style={{

                              fontSize: 13, fontWeight: 700,

                              color: 'var(--text)', margin: '0 0 6px',

                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',

                            }}>

                              {(() => {

                                const t = job.project_brief?.topic || job.source_filename;

                                if (t && !/[0-9a-f]{8}-[0-9a-f]{4}/i.test(t)) return t;

                                return 'Analysis';

                              })()}

                            </h4>

                            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>

                              <span style={{

                                padding: '2px 8px', borderRadius: 6,

                                fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',

                                background: `${accentColor}18`,

                                color: accentColor,

                                border: `1px solid ${accentColor}35`,

                              }}>{status.label}</span>

                              {job.n_rows && (

                                <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{job.n_rows.toLocaleString()} rows</span>

                              )}

                              {job.created_at && (

                                <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{new Date(job.created_at).toLocaleDateString()}</span>

                              )}

                            </div>

                          </div>



                          <button

                            onClick={(e) => handleDeleteJob(e, job.id)}

                            disabled={deletingId === job.id}

                            title="Delete Analysis"

                            style={{

                              padding: 7, borderRadius: 8, background: 'transparent',

                              border: '1px solid transparent', color: 'var(--text-3)',

                              cursor: 'pointer', transition: 'all 0.15s', flexShrink: 0,

                            }}

                            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.borderColor = 'rgba(239,68,68,0.2)'; }}

                            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.borderColor = 'transparent'; }}

                          >

                            {deletingId === job.id

                              ? <RiLoader4Line size={14} style={{ animation: 'spin 1s linear infinite' }} />

                              : <RiDeleteBinFill size={14} />}

                          </button>

                        </div>



                        {/* Running shimmer bar */}

                        {isRunning && (

                          <div style={{ marginTop: 10, height: 3, borderRadius: 2, background: 'var(--surface-2)', overflow: 'hidden', position: 'relative' }}>

                            <div style={{

                              position: 'absolute', inset: 0, width: '40%',

                              background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,

                              animation: 'shimmerBar 1.8s ease-in-out infinite',

                            }} />

                          </div>

                        )}

                        {isReview && (

                          <div style={{

                            marginTop: 8, padding: '4px 10px', borderRadius: 6,

                            background: 'rgba(245,158,11,0.08)', border: '1px solid var(--border)',

                            fontSize: 11, fontWeight: 600, color: '#f59e0b',

                            display: 'inline-block',

                          }}>

                            {'\u26a0\ufe0f'} Action required {'\u2014'} click to review

                          </div>

                        )}

                      </div>

                    </Link>

                  );

                })}



                {jobs.length > 6 && (

                  <Link href="/reports">

                    <button style={{

                      width: '100%', padding: '11px',

                      borderRadius: 12, border: '1px solid var(--border)',

                      background: 'var(--surface-2)', color: 'var(--text-2)',

                      fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',

                    }}

                    onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--brand)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--brand)'; }}

                    onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-2)'; }}

                    >

                      View all {jobs.length} analyses →

                    </button>

                  </Link>

                )}

              </div>

            )}

          </div>

        </div>

      </div>

    </AppLayout>

  );

}

